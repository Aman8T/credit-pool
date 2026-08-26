from __future__ import annotations

import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fake_agents"


def fake(name: str) -> str:
    return str((FIXTURES / name).resolve())


def write_config(
    repo: Path,
    *,
    claude_bin: str,
    codex_bin: str,
    verification: list[str] | None = None,
    max_attempts: int = 3,
    timeout: int = 30,
    cursor_enabled: bool = False,
) -> None:
    verify = verification if verification is not None else []
    verify_toml = json.dumps(verify)
    (repo / ".creditpool.toml").write_text(
        f"""
[creditpool]
max_attempts = {max_attempts}
task_timeout_seconds = {timeout}
artifact_dir = ".creditpool"
verification_command = {verify_toml}
fallback_on = ["rate_limit", "unavailable"]
branch_prefix = "creditpool"

[agents]
priority = ["claude", "codex"]

[agents.claude]
enabled = true
bin = {json.dumps(Path(claude_bin).as_posix())}

[agents.codex]
enabled = true
bin = {json.dumps(Path(codex_bin).as_posix())}

[agents.cursor]
enabled = {str(cursor_enabled).lower()}
bin = "agent"
allow_force = false
""",
        encoding="utf-8",
    )


def plant_secret_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secretTESTVALUE123")
    monkeypatch.setenv("AUTHORIZATION", "Bearer super-secret-token")
