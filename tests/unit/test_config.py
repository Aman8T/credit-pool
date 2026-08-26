from pathlib import Path

import pytest
from pydantic import ValidationError

from creditpool.config import AppConfig, write_default_config


def test_rejects_danger_full_access() -> None:
    with pytest.raises(ValidationError):
        AppConfig.model_validate(
            {"agents": {"codex": {"sandbox": "danger-full-access"}}}
        )


def test_rejects_bypass_permissions() -> None:
    with pytest.raises(ValidationError):
        AppConfig.model_validate(
            {"agents": {"claude": {"permission_mode": "bypassPermissions"}}}
        )


def test_write_default_roundtrip(tmp_path: Path) -> None:
    write_default_config(tmp_path)
    from creditpool.config import load_config

    cfg = load_config(tmp_path)
    assert cfg.agents.priority == ["claude", "codex"]
    assert cfg.agents.cursor.enabled is False
    assert cfg.creditpool.verification_command == []
