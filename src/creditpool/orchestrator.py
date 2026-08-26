from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from creditpool.adapters import get_adapter
from creditpool.adapters.base import RunContext
from creditpool.classify import classify
from creditpool.config import AppConfig
from creditpool.gitutil import add_worktree, head_commit
from creditpool.handoff import build_handoff, continuation_prompt, write_handoff
from creditpool.ledger import Ledger
from creditpool.models import Availability, TaskState, Termination
from creditpool.process import run_argv
from creditpool.redact import redact_text


@dataclass
class RunOutcome:
    task_id: str
    state: TaskState
    branch: str
    worktree: Path
    message: str


def new_task_id() -> str:
    return uuid.uuid4().hex[:12]


def artifact_paths(repo_root: Path, artifact_dir: str, task_id: str, attempt_n: int) -> Path:
    return repo_root / artifact_dir / "artifacts" / task_id / "attempts" / str(attempt_n)


def _eligible_agents(
    config: AppConfig,
    *,
    pin: str | None,
    skipped: set[str],
) -> list[str]:
    if pin:
        order = [pin]
    else:
        order = list(config.agents.priority)
    out: list[str] = []
    for agent_id in order:
        if agent_id in skipped:
            continue
        if not config.agent_enabled(agent_id):
            continue
        adapter = get_adapter(agent_id, config)
        detected = adapter.detect()
        if not detected.installed:
            continue
        avail = adapter.availability()
        if avail in {
            Availability.unavailable,
            Availability.unauthenticated,
            Availability.limited,
        }:
            continue
        out.append(agent_id)
    return out


def run_task(
    *,
    repo_root: Path,
    config: AppConfig,
    prompt: str,
    acceptance: str | None,
    pin_agent: str | None,
    max_attempts: int | None,
    dry_run: bool,
) -> RunOutcome:
    task_id = new_task_id()
    branch = f"{config.creditpool.branch_prefix}/{task_id}"
    worktree = repo_root / config.creditpool.artifact_dir / "worktrees" / task_id
    base = head_commit(repo_root)
    limit = max_attempts or config.creditpool.max_attempts
    fallback_on = set(config.creditpool.fallback_on)

    if dry_run:
        skipped: set[str] = set()
        agents = _eligible_agents(config, pin=pin_agent, skipped=skipped)
        lines = []
        for agent_id in agents:
            adapter = get_adapter(agent_id, config)
            ctx = RunContext(
                worktree=worktree,
                prompt=prompt,
                handoff_path=None,
                timeout_seconds=config.creditpool.task_timeout_seconds,
                stdout_path=Path("stdout.log"),
                stderr_path=Path("stderr.log"),
            )
            lines.append(" ".join(adapter.build_command(ctx)))
        return RunOutcome(
            task_id="dry-run",
            state=TaskState.pending,
            branch=branch,
            worktree=worktree,
            message="dry-run argv:\n" + "\n".join(lines or ["(no eligible agents)"]),
        )

    ledger_path = repo_root / config.creditpool.artifact_dir / "creditpool.sqlite"
    ledger = Ledger(ledger_path)

    add_worktree(repo_root, worktree, branch)
    ledger.insert_task(
        task_id=task_id,
        prompt=prompt,
        acceptance=acceptance,
        repo_root=str(repo_root),
        base_commit=base,
        branch=branch,
        worktree_path=str(worktree),
    )
    ledger.set_state(task_id, TaskState.running)

    skipped: set[str] = set()
    last_error = "no eligible agents"
    last_attempt_id: int | None = None
    used_handoff = False

    try:
        while True:
            attempts = ledger.attempts_for(task_id)
            if len(attempts) >= limit:
                ledger.set_state(task_id, TaskState.failed, "max_attempts exceeded")
                return RunOutcome(
                    task_id=task_id,
                    state=TaskState.failed,
                    branch=branch,
                    worktree=worktree,
                    message=f"failed: max_attempts ({limit}) exceeded. {last_error}",
                )
            agents = _eligible_agents(config, pin=pin_agent, skipped=skipped)
            if not agents:
                ledger.set_state(task_id, TaskState.failed, "agents_exhausted")
                return RunOutcome(
                    task_id=task_id,
                    state=TaskState.failed,
                    branch=branch,
                    worktree=worktree,
                    message=f"failed: agents_exhausted. {last_error}",
                )
            agent_id = agents[0]
            adapter = get_adapter(agent_id, config)
            attempt = ledger.start_attempt(task_id, agent_id)
            attempt_dir = artifact_paths(
                repo_root, config.creditpool.artifact_dir, task_id, attempt.n
            )
            stdout_path = attempt_dir / "stdout.log"
            stderr_path = attempt_dir / "stderr.log"
            attempt_dir.mkdir(parents=True, exist_ok=True)
            prompt_text = (
                continuation_prompt(prompt, acceptance) if used_handoff else _initial_prompt(prompt, acceptance)
            )
            ctx = RunContext(
                worktree=worktree,
                prompt=prompt_text,
                handoff_path=worktree / ".creditpool-handoff.json"
                if (worktree / ".creditpool-handoff.json").exists()
                else None,
                timeout_seconds=config.creditpool.task_timeout_seconds,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )
            argv = adapter.build_command(ctx)
            (attempt_dir / "argv.json").write_text(
                json.dumps(argv[:-1] + ["<prompt>"], indent=2), encoding="utf-8"
            )
            code, timed_out, cancelled, duration_ms = run_argv(
                argv,
                cwd=worktree,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                timeout_seconds=config.creditpool.task_timeout_seconds,
            )
            stdout = stdout_path.read_text(encoding="utf-8")
            stderr = stderr_path.read_text(encoding="utf-8")
            parsed = adapter.parse_output(stdout, stderr, code)
            termination = classify(
                parsed,
                exit_code=code,
                timed_out=timed_out,
                cancelled=cancelled,
                stderr=stderr,
            )
            (attempt_dir / "events.jsonl").write_text(
                "\n".join(json.dumps(e, default=str) for e in parsed.events),
                encoding="utf-8",
            )
            ledger.finish_attempt(
                attempt.id,
                exit_code=code,
                termination=termination,
                stdout_path=str(stdout_path),
                stderr_path=str(stderr_path),
                native_session_id=parsed.session_id,
                duration_ms=duration_ms,
                events=parsed.events,
            )
            last_attempt_id = attempt.id
            last_error = f"{agent_id}: {termination.value}"

            if termination == Termination.cancelled:
                ledger.set_state(task_id, TaskState.cancelled, last_error)
                return RunOutcome(
                    task_id=task_id,
                    state=TaskState.cancelled,
                    branch=branch,
                    worktree=worktree,
                    message="cancelled",
                )

            if termination == Termination.success:
                return _verify(
                    ledger,
                    config,
                    repo_root,
                    task_id,
                    worktree,
                    branch,
                    last_attempt_id,
                )

            if termination.value in fallback_on and not pin_agent:
                ledger.set_state(task_id, TaskState.handing_off, last_error)
                packet = build_handoff(
                    task_id=task_id,
                    prompt=prompt,
                    acceptance=acceptance,
                    repo_root=repo_root,
                    base_commit=base,
                    branch=branch,
                    worktree=worktree,
                    previous_agent=agent_id,
                    attempt_n=attempt.n,
                    termination=termination.value,
                    error_information=redact_text(
                        parsed.error_message or parsed.result_text or stderr[:2000] or termination.value
                    ),
                    result_text=parsed.result_text,
                )
                art = repo_root / config.creditpool.artifact_dir / "artifacts" / task_id
                path = write_handoff(worktree, art, packet)
                ledger.insert_handoff(
                    task_id=task_id,
                    from_attempt_id=attempt.id,
                    path=str(path),
                    payload=packet,
                )
                skipped.add(agent_id)
                used_handoff = True
                ledger.set_state(task_id, TaskState.running)
                continue

            ledger.set_state(task_id, TaskState.failed, last_error)
            return RunOutcome(
                task_id=task_id,
                state=TaskState.failed,
                branch=branch,
                worktree=worktree,
                message=(
                    f"failed ({termination.value}) on {agent_id}. "
                    "Automatic fallback only runs for recognized rate_limit/unavailable."
                ),
            )
    except KeyboardInterrupt:
        ledger.set_state(task_id, TaskState.cancelled, "interrupted")
        return RunOutcome(
            task_id=task_id,
            state=TaskState.cancelled,
            branch=branch,
            worktree=worktree,
            message="cancelled",
        )
    finally:
        ledger.close()


def _initial_prompt(prompt: str, acceptance: str | None) -> str:
    extra = ""
    if acceptance:
        extra = f"\n\nAcceptance criteria:\n{acceptance}"
    return (
        f"{prompt}{extra}\n\n"
        "Do not merge, push, or open a pull request. Leave changes in the working tree."
    )


def _verify(
    ledger: Ledger,
    config: AppConfig,
    repo_root: Path,
    task_id: str,
    worktree: Path,
    branch: str,
    attempt_id: int | None,
) -> RunOutcome:
    cmd = list(config.creditpool.verification_command)
    if not cmd:
        ledger.set_state(task_id, TaskState.completed)
        return RunOutcome(
            task_id=task_id,
            state=TaskState.completed,
            branch=branch,
            worktree=worktree,
            message=f"completed without verification. branch {branch} worktree {worktree}",
        )
    ledger.set_state(task_id, TaskState.verifying)
    log_dir = repo_root / config.creditpool.artifact_dir / "artifacts" / task_id
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / "verification.stdout.log"
    stderr_path = log_dir / "verification.stderr.log"
    code, timed_out, _, _ = run_argv(
        cmd,
        cwd=worktree,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        timeout_seconds=config.creditpool.task_timeout_seconds,
    )
    exit_code = -1 if timed_out or code is None else code
    ledger.insert_verification(
        task_id=task_id,
        attempt_id=attempt_id,
        command=cmd,
        exit_code=exit_code,
        log_path=str(stdout_path),
    )
    if timed_out or exit_code != 0:
        ledger.set_state(task_id, TaskState.failed, "verification_failed")
        return RunOutcome(
            task_id=task_id,
            state=TaskState.failed,
            branch=branch,
            worktree=worktree,
            message=f"verification failed (exit {exit_code}). branch {branch} was not merged.",
        )
    ledger.set_state(task_id, TaskState.completed)
    return RunOutcome(
        task_id=task_id,
        state=TaskState.completed,
        branch=branch,
        worktree=worktree,
        message=f"completed. review branch {branch} at {worktree} (not merged).",
    )
