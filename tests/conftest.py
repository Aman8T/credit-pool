from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "commit.gpgsign", "false")
    (repo / "app.txt").write_text("stage=none\n", encoding="utf-8")
    git(repo, "add", "app.txt")
    git(repo, "commit", "-m", "init")
    return repo
