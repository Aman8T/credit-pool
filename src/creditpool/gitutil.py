from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(RuntimeError):
    pass


def _git(cwd: Path, args: list[str]) -> str:
    proc = subprocess.run(  # noqa: S603
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise GitError(proc.stderr.strip() or proc.stdout.strip() or "git failed")
    return proc.stdout


def repo_root(start: Path) -> Path:
    out = _git(start, ["rev-parse", "--show-toplevel"]).strip()
    return Path(out)


def head_commit(repo: Path) -> str:
    return _git(repo, ["rev-parse", "HEAD"]).strip()


def add_worktree(repo: Path, worktree: Path, branch: str) -> None:
    worktree.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, ["worktree", "add", "-b", branch, str(worktree), "HEAD"])


def status_porcelain(worktree: Path) -> str:
    return _git(worktree, ["status", "--porcelain=v1", "-uall"])


def diff_cached_and_worktree(worktree: Path) -> str:
    tracked = _git(worktree, ["diff"])
    return tracked


def changed_files(worktree: Path) -> list[str]:
    lines = status_porcelain(worktree).splitlines()
    files: list[str] = []
    for line in lines:
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append(path)
    return files


def diff_stat(worktree: Path) -> str:
    return _git(worktree, ["diff", "--stat"])
