from __future__ import annotations

import json
import sys
from pathlib import Path


def _handle_version() -> bool:
    if "--version" in sys.argv or "-v" in sys.argv:
        print("fake-claude 0.0.1")
        return True
    return False


def _write_stage() -> None:
    Path("app.txt").write_text("stage=claude\n", encoding="utf-8")


if __name__ == "__main__":
    if _handle_version():
        raise SystemExit(0)
    _write_stage()
    print(
        json.dumps(
            {
                "type": "error",
                "error": "rate_limit",
                "session_id": "sess-claude",
            }
        )
    )
    print(
        json.dumps(
            {
                "type": "result",
                "subtype": "error",
                "is_error": True,
                "result": "Claude Code usage limit reached",
                "session_id": "sess-claude",
            }
        )
    )
    raise SystemExit(1)
