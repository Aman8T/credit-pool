from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from creditpool import __version__, gitutil
from creditpool.adapters import get_adapter
from creditpool.config import (
    CONFIG_NAME,
    STATE_DIRNAME,
    AppConfig,
    load_config,
    write_default_config,
)
from creditpool.ledger import Ledger
from creditpool.orchestrator import run_task

app = typer.Typer(
    name="creditpool",
    no_args_is_help=True,
    help="Local-first sequential runner for official coding CLIs you already pay for.",
)


def _repo() -> Path:
    try:
        return gitutil.repo_root(Path.cwd())
    except gitutil.GitError as exc:
        raise typer.BadParameter(f"not a git repository: {exc}") from exc


def _config(repo: Path) -> AppConfig:
    try:
        return load_config(repo)
    except FileNotFoundError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except Exception as exc:  # pydantic
        raise typer.BadParameter(f"invalid {CONFIG_NAME}: {exc}") from exc


@app.command()
def init(
    force: bool = typer.Option(False, help="Overwrite an existing config file."),
) -> None:
    """Create repository config, state dir, and gitignore entries."""
    repo = _repo()
    write_default_config(repo, force=force)
    state = repo / STATE_DIRNAME
    state.mkdir(exist_ok=True)
    gi = repo / ".gitignore"
    snippet = "\n".join(
        [
            "",
            "# CreditPool local state (ledger, worktrees, logs)",
            ".creditpool/",
            "",
        ]
    )
    existing = gi.read_text(encoding="utf-8") if gi.exists() else ""
    if ".creditpool/" not in existing:
        gi.write_text(existing + snippet, encoding="utf-8")
    typer.echo(f"wrote {repo / CONFIG_NAME}")
    typer.echo(f"state directory: {state} (gitignored; not committed by default)")
    typer.echo("Credentials stay in vendor CLIs. Do not add keys to .creditpool.toml.")


@app.command()
def doctor() -> None:
    """Check git, config, and installed vendor CLIs. Quota is reported as unknown."""
    repo = _repo()
    typer.echo(f"git repository: {repo}")
    try:
        config = load_config(repo)
        typer.echo(f"config: {repo / CONFIG_NAME} ok")
    except FileNotFoundError:
        typer.echo(f"config: missing {CONFIG_NAME} (run creditpool init)")
        config = AppConfig()
    except Exception as exc:
        typer.echo(f"config: invalid ({exc})")
        raise typer.Exit(code=1) from exc

    for agent_id in ("claude", "codex", "cursor"):
        adapter = get_adapter(agent_id, config)
        detected = adapter.detect()
        avail = adapter.availability()
        enabled = config.agent_enabled(agent_id)
        version = detected.version or "unknown"
        installed = "yes" if detected.installed else "no"
        typer.echo(
            f"{agent_id}: enabled={enabled} installed={installed} "
            f"version={version!s} availability={avail.value}"
        )
        if detected.notes:
            typer.echo(f"  note: {detected.notes}")
    typer.echo(
        "quota: unknown (no official subscriber quota CLI is used; "
        "unknown is not treated as zero)"
    )


@app.command()
def status() -> None:
    """Show config priority and the latest task."""
    repo = _repo()
    config = _config(repo)
    typer.echo(f"repo: {repo}")
    typer.echo(f"priority: {', '.join(config.agents.priority)}")
    db = repo / config.creditpool.artifact_dir / "creditpool.sqlite"
    if not db.is_file():
        typer.echo("tasks: none")
        return
    ledger = Ledger(db)
    try:
        latest = ledger.latest_task()
        if not latest:
            typer.echo("tasks: none")
            return
        typer.echo(
            f"latest: {latest.id} state={latest.state} branch={latest.branch}"
        )
    finally:
        ledger.close()


@app.command("run")
def run_cmd(
    task: str = typer.Argument(..., help="Repository task for the coding agent."),
    accept: Optional[str] = typer.Option(None, "--accept", help="Acceptance criteria."),
    agent: Optional[str] = typer.Option(
        None, "--agent", help="Pin a single agent (disables fallback)."
    ),
    max_attempts: Optional[int] = typer.Option(None, "--max-attempts"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print argv; do not spawn."),
) -> None:
    """Run a task in an isolated git worktree with sequential agent fallback."""
    repo = _repo()
    config = _config(repo)
    outcome = run_task(
        repo_root=repo,
        config=config,
        prompt=task,
        acceptance=accept,
        pin_agent=agent,
        max_attempts=max_attempts,
        dry_run=dry_run,
    )
    typer.echo(outcome.message)
    typer.echo(f"task_id={outcome.task_id} state={outcome.state.value}")
    if outcome.state.value in {"failed", "cancelled"} and not dry_run:
        raise typer.Exit(code=1)


@app.command()
def tasks() -> None:
    """List recorded tasks."""
    repo = _repo()
    config = _config(repo)
    db = repo / config.creditpool.artifact_dir / "creditpool.sqlite"
    if not db.is_file():
        typer.echo("(no tasks)")
        return
    ledger = Ledger(db)
    try:
        rows = ledger.list_tasks()
        if not rows:
            typer.echo("(no tasks)")
            return
        for row in rows:
            typer.echo(f"{row.id}\t{row.state}\t{row.branch}\t{row.prompt[:60]}")
    finally:
        ledger.close()


@app.command()
def show(task_id: str = typer.Argument(..., help="Task id from `creditpool tasks`.")) -> None:
    """Show a task, attempts, handoffs, and verification."""
    repo = _repo()
    config = _config(repo)
    db = repo / config.creditpool.artifact_dir / "creditpool.sqlite"
    ledger = Ledger(db)
    try:
        task = ledger.get_task(task_id)
        if task is None:
            typer.echo(f"unknown task: {task_id}")
            raise typer.Exit(code=1)
        typer.echo(json.dumps(task.__dict__, indent=2))
        for attempt in ledger.attempts_for(task_id):
            typer.echo(
                f"attempt {attempt.n} agent={attempt.agent_id} "
                f"termination={attempt.termination} exit={attempt.exit_code}"
            )
        for handoff in ledger.handoffs_for(task_id):
            typer.echo(f"handoff: {handoff.get('path')}")
        for ver in ledger.verifications_for(task_id):
            typer.echo(
                f"verification exit={ver.get('exit_code')} cmd={ver.get('command')}"
            )
    finally:
        ledger.close()


@app.callback()
def _version_callback(
    version: bool = typer.Option(False, "--version", help="Show version and exit."),
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
