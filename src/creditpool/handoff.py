from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from creditpool import gitutil


def build_handoff(
    *,
    task_id: str,
    prompt: str,
    acceptance: str | None,
    repo_root: Path,
    base_commit: str,
    branch: str,
    worktree: Path,
    previous_agent: str,
    attempt_n: int,
    termination: str,
    error_information: str | None,
    result_text: str | None,
    verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    changed = gitutil.changed_files(worktree)
    diff = gitutil.diff_cached_and_worktree(worktree)
    stat = gitutil.diff_stat(worktree)
    status = gitutil.status_porcelain(worktree)
    max_diff = 80_000
    if len(diff) > max_diff:
        diff_summary = diff[:max_diff] + "\n... [truncated]\n"
    else:
        diff_summary = diff
    completed = result_text.strip() if result_text and result_text.strip() else "unknown"
    remaining = (
        "unknown — continue the original task from the current worktree and this packet"
    )
    packet = {
        "schema": "creditpool.handoff.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "task_id": task_id,
        "original_task": prompt,
        "acceptance_criteria": acceptance,
        "repository": str(repo_root),
        "base_commit": base_commit,
        "branch": branch,
        "worktree": str(worktree),
        "completed_work": completed,
        "remaining_work": remaining,
        "changed_files": changed,
        "git_status": status,
        "diff_stat": stat,
        "current_diff_summary": diff_summary,
        "test_results": verification or "unknown",
        "error_information": error_information,
        "termination": termination,
        "previous_agent": previous_agent,
        "previous_attempt": attempt_n,
    }
    return packet


def write_handoff(worktree: Path, artifacts: Path, packet: dict[str, Any]) -> Path:
    artifacts.mkdir(parents=True, exist_ok=True)
    json_path = artifacts / "handoff.json"
    md_path = artifacts / "handoff.md"
    json_path.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    md_path.write_text(_to_markdown(packet), encoding="utf-8")
    (worktree / ".creditpool-handoff.json").write_text(
        json.dumps(packet, indent=2), encoding="utf-8"
    )
    return json_path


def _to_markdown(packet: dict[str, Any]) -> str:
    files = "\n".join(f"- `{p}`" for p in packet.get("changed_files") or []) or "- (none)"
    return f"""# CreditPool handoff

- Task ID: `{packet.get("task_id")}`
- Previous agent: `{packet.get("previous_agent")}` (attempt {packet.get("previous_attempt")})
- Termination: `{packet.get("termination")}`
- Repo: `{packet.get("repository")}`
- Base commit: `{packet.get("base_commit")}`
- Branch: `{packet.get("branch")}`
- Worktree: `{packet.get("worktree")}`

## Original task

{packet.get("original_task")}

## Acceptance criteria

{packet.get("acceptance_criteria") or "(none provided)"}

## Completed work

{packet.get("completed_work")}

## Remaining work

{packet.get("remaining_work")}

## Changed files

{files}

## Diff stat

```
{packet.get("diff_stat") or "(empty)"}
```

## Error information

{packet.get("error_information") or "(none)"}
"""


def continuation_prompt(original: str, acceptance: str | None) -> str:
    criteria = acceptance or "(none provided)"
    return (
        "You are continuing a repository task coordinated by CreditPool.\n\n"
        "## Original task\n"
        f"{original}\n\n"
        "## Acceptance criteria\n"
        f"{criteria}\n\n"
        "If `.creditpool-handoff.json` exists in the workspace, read it and continue "
        "from remaining work. Do not revert completed work unless required to finish "
        "the task. Do not merge, push, or open a pull request.\n"
    )
