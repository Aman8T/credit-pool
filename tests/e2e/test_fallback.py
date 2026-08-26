from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from creditpool.cli import app
from creditpool.ledger import Ledger
from tests.helpers import fake, plant_secret_env, write_config

runner = CliRunner()


def test_init_and_doctor(tmp_repo: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_repo)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert (tmp_repo / ".creditpool.toml").is_file()
    gi = (tmp_repo / ".gitignore").read_text(encoding="utf-8")
    assert ".creditpool/" in gi
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "quota: unknown" in result.stdout


def test_hero_fallback_claude_to_codex(tmp_repo: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_repo)
    plant_secret_env(monkeypatch)
    verify = tmp_repo / "verify.py"
    verify.write_text(
        "from pathlib import Path\n"
        "text = Path('app.txt').read_text()\n"
        "assert 'stage=claude' in text\n"
        "assert 'stage=codex' in text\n",
        encoding="utf-8",
    )
    import sys

    write_config(
        tmp_repo,
        claude_bin=fake("claude_ratelimit.py"),
        codex_bin=fake("codex_success.py"),
        verification=[sys.executable, str(verify)],
    )
    result = runner.invoke(app, ["run", "add both stages to app.txt"])
    assert result.exception is None, result.exception
    assert result.exit_code == 0, result.output
    assert "completed" in result.output
    db = Ledger(tmp_repo / ".creditpool" / "creditpool.sqlite")
    tasks = db.list_tasks()
    assert len(tasks) == 1
    task = tasks[0]
    attempts = db.attempts_for(task.id)
    assert len(attempts) == 2
    assert attempts[0].agent_id == "claude"
    assert attempts[0].termination == "rate_limit"
    assert attempts[1].agent_id == "codex"
    assert attempts[1].termination == "success"
    handoffs = db.handoffs_for(task.id)
    assert len(handoffs) == 1
    worktree = Path(task.worktree_path)
    text = (worktree / "app.txt").read_text(encoding="utf-8")
    assert "stage=claude" in text
    assert "stage=codex" in text
    # original branch file unchanged
    assert (tmp_repo / "app.txt").read_text(encoding="utf-8") == "stage=none\n"
    # no merge: HEAD still original
    import subprocess

    branch = subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=tmp_repo, text=True
    ).strip()
    assert not branch.startswith("creditpool/")
    # secrets not in artifacts
    artifacts = tmp_repo / ".creditpool" / "artifacts"
    blob = ""
    for path in artifacts.rglob("*"):
        if path.is_file():
            blob += path.read_text(encoding="utf-8", errors="replace")
    assert "sk-secretTESTVALUE123" not in blob
    assert "super-secret-token" not in blob
    assert (worktree / ".creditpool-handoff.json").is_file()
    show = runner.invoke(app, ["show", task.id])
    assert show.exit_code == 0
    assert "claude" in show.output
    db.close()


def test_auth_does_not_fallback(tmp_repo: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_repo)
    write_config(
        tmp_repo,
        claude_bin=fake("claude_auth.py"),
        codex_bin=fake("codex_success.py"),
    )
    result = runner.invoke(app, ["run", "should fail auth"])
    assert result.exit_code == 1
    db = Ledger(tmp_repo / ".creditpool" / "creditpool.sqlite")
    task = db.list_tasks()[0]
    attempts = db.attempts_for(task.id)
    assert len(attempts) == 1
    assert attempts[0].termination == "auth"
    db.close()


def test_unavailable_falls_back(tmp_repo: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_repo)
    write_config(
        tmp_repo,
        claude_bin=fake("claude_unavailable.py"),
        codex_bin=fake("claude_success.py"),
    )
    result = runner.invoke(app, ["run", "task"])
    assert result.exit_code == 0, result.output
    db = Ledger(tmp_repo / ".creditpool" / "creditpool.sqlite")
    attempts = db.attempts_for(db.list_tasks()[0].id)
    assert attempts[0].termination == "unavailable"
    assert attempts[1].termination == "success"
    db.close()


def test_malformed_no_fallback(tmp_repo: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_repo)
    write_config(
        tmp_repo,
        claude_bin=fake("claude_malformed.py"),
        codex_bin=fake("codex_success.py"),
    )
    result = runner.invoke(app, ["run", "task"])
    assert result.exit_code == 1
    db = Ledger(tmp_repo / ".creditpool" / "creditpool.sqlite")
    attempts = db.attempts_for(db.list_tasks()[0].id)
    assert len(attempts) == 1
    assert attempts[0].termination == "malformed"
    db.close()


def test_timeout(tmp_repo: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_repo)
    write_config(
        tmp_repo,
        claude_bin=fake("claude_timeout.py"),
        codex_bin=fake("codex_success.py"),
        timeout=1,
    )
    result = runner.invoke(app, ["run", "task"])
    assert result.exit_code == 1
    db = Ledger(tmp_repo / ".creditpool" / "creditpool.sqlite")
    attempts = db.attempts_for(db.list_tasks()[0].id)
    assert attempts[0].termination == "timeout"
    db.close()


def test_verification_failure(tmp_repo: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_repo)
    import sys

    fail = tmp_repo / "fail.py"
    fail.write_text("raise SystemExit(1)\n", encoding="utf-8")
    write_config(
        tmp_repo,
        claude_bin=fake("claude_success.py"),
        codex_bin=fake("codex_success.py"),
        verification=[sys.executable, str(fail)],
    )
    result = runner.invoke(app, ["run", "task"])
    assert result.exit_code == 1
    assert "verification" in result.output
    db = Ledger(tmp_repo / ".creditpool" / "creditpool.sqlite")
    task = db.list_tasks()[0]
    assert task.state == "failed"
    assert len(db.attempts_for(task.id)) == 1
    db.close()


def test_all_agents_exhausted(tmp_repo: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_repo)
    write_config(
        tmp_repo,
        claude_bin=fake("claude_ratelimit.py"),
        codex_bin=fake("codex_ratelimit.py"),
    )
    result = runner.invoke(app, ["run", "task"])
    assert result.exit_code == 1
    db = Ledger(tmp_repo / ".creditpool" / "creditpool.sqlite")
    task = db.list_tasks()[0]
    assert len(db.attempts_for(task.id)) == 2
    assert task.state == "failed"
    db.close()
