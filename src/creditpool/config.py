from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

CONFIG_NAME = ".creditpool.toml"
STATE_DIRNAME = ".creditpool"
FORBIDDEN_SANDBOX = {"danger-full-access"}
FORBIDDEN_PERMISSION = {"bypassPermissions", "bypass-permissions"}

DEFAULT_TOML = """\
# CreditPool repository configuration.
# Do not put API keys, OAuth tokens, cookies, or session secrets here.
# Each vendor CLI manages its own authentication.

[creditpool]
max_attempts = 3
task_timeout_seconds = 1800
artifact_dir = ".creditpool"
verification_command = []
fallback_on = ["rate_limit", "unavailable"]
branch_prefix = "creditpool"

[agents]
priority = ["claude", "codex"]

[agents.claude]
enabled = true
bin = "claude"
permission_mode = "acceptEdits"
allowed_tools = ["Read", "Edit", "Write", "Glob", "Grep", "Bash"]

[agents.codex]
enabled = true
bin = "codex"
sandbox = "workspace-write"
approval_policy = "never"

[agents.cursor]
enabled = false
bin = "agent"
allow_force = false
"""


class ClaudeAgentConfig(BaseModel):
    enabled: bool = True
    bin: str = "claude"
    permission_mode: str = "acceptEdits"
    allowed_tools: list[str] = Field(
        default_factory=lambda: ["Read", "Edit", "Write", "Glob", "Grep", "Bash"]
    )

    @field_validator("permission_mode")
    @classmethod
    def _permission_ok(cls, value: str) -> str:
        if value in FORBIDDEN_PERMISSION:
            raise ValueError(
                "bypassPermissions / --dangerously-skip-permissions is not allowed"
            )
        return value


class CodexAgentConfig(BaseModel):
    enabled: bool = True
    bin: str = "codex"
    sandbox: str = "workspace-write"
    approval_policy: str = "never"

    @field_validator("sandbox")
    @classmethod
    def _sandbox_ok(cls, value: str) -> str:
        if value in FORBIDDEN_SANDBOX:
            raise ValueError("sandbox danger-full-access is not allowed in V1")
        return value


class CursorAgentConfig(BaseModel):
    enabled: bool = False
    bin: str = "agent"
    allow_force: bool = False


class AgentsConfig(BaseModel):
    priority: list[str] = Field(default_factory=lambda: ["claude", "codex"])
    claude: ClaudeAgentConfig = Field(default_factory=ClaudeAgentConfig)
    codex: CodexAgentConfig = Field(default_factory=CodexAgentConfig)
    cursor: CursorAgentConfig = Field(default_factory=CursorAgentConfig)


class CreditPoolSection(BaseModel):
    max_attempts: int = 3
    task_timeout_seconds: int = 1800
    artifact_dir: str = STATE_DIRNAME
    verification_command: list[str] = Field(default_factory=list)
    fallback_on: list[str] = Field(default_factory=lambda: ["rate_limit", "unavailable"])
    branch_prefix: str = "creditpool"

    @field_validator("max_attempts")
    @classmethod
    def _attempts(cls, value: int) -> int:
        if value < 1:
            raise ValueError("max_attempts must be >= 1")
        return value

    @field_validator("fallback_on")
    @classmethod
    def _fallback(cls, value: list[str]) -> list[str]:
        allowed = {"rate_limit", "unavailable"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unsupported fallback_on values: {sorted(unknown)}")
        return value

    @field_validator("verification_command")
    @classmethod
    def _verify_argv(cls, value: list[str]) -> list[str]:
        if any(not isinstance(item, str) or not item for item in value):
            raise ValueError("verification_command must be a list of non-empty strings")
        return value


class AppConfig(BaseModel):
    creditpool: CreditPoolSection = Field(default_factory=CreditPoolSection)
    agents: AgentsConfig = Field(default_factory=AgentsConfig)

    @model_validator(mode="after")
    def _priority_known(self) -> AppConfig:
        known = {"claude", "codex", "cursor"}
        for name in self.agents.priority:
            if name not in known:
                raise ValueError(f"unknown agent in priority: {name}")
        return self

    def agent_enabled(self, agent_id: str) -> bool:
        if agent_id == "claude":
            return self.agents.claude.enabled
        if agent_id == "codex":
            return self.agents.codex.enabled
        if agent_id == "cursor":
            return self.agents.cursor.enabled
        return False

    def bin_for(self, agent_id: str) -> str:
        env_key = f"CREDITPOOL_{agent_id.upper()}_BIN"
        if os.environ.get(env_key):
            return os.environ[env_key]
        if agent_id == "claude":
            return self.agents.claude.bin
        if agent_id == "codex":
            return self.agents.codex.bin
        if agent_id == "cursor":
            return self.agents.cursor.bin
        raise KeyError(agent_id)


def resolve_bin_argv(bin_spec: str) -> list[str]:
    path = Path(bin_spec)
    if path.suffix.lower() == ".py":
        return [sys.executable, str(path)]
    return [bin_spec]


def find_repo_root(start: Path | None = None) -> Path:
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / ".git").exists():
            return candidate
    raise FileNotFoundError("not a git repository")


def config_path(repo_root: Path) -> Path:
    return repo_root / CONFIG_NAME


def load_config(repo_root: Path) -> AppConfig:
    path = config_path(repo_root)
    if not path.is_file():
        raise FileNotFoundError(
            f"missing {CONFIG_NAME}; run `creditpool init` in the repository root"
        )
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return AppConfig.model_validate(_normalize_toml(data))


def _normalize_toml(data: dict[str, Any]) -> dict[str, Any]:
    agents = data.get("agents") or {}
    nested = {
        "priority": agents.get("priority", ["claude", "codex"]),
        "claude": agents.get("claude") or {},
        "codex": agents.get("codex") or {},
        "cursor": agents.get("cursor") or {},
    }
    return {"creditpool": data.get("creditpool") or {}, "agents": nested}


def write_default_config(repo_root: Path, force: bool = False) -> Path:
    path = config_path(repo_root)
    if path.exists() and not force:
        return path
    path.write_text(DEFAULT_TOML, encoding="utf-8")
    return path
