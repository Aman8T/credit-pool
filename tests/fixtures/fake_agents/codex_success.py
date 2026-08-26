from __future__ import annotations

import json
import sys
from pathlib import Path

if "--version" in sys.argv:
    print("fake-codex 0.0.1")
    raise SystemExit(0)

path = Path("app.txt")
existing = path.read_text(encoding="utf-8") if path.exists() else ""
if "stage=claude" not in existing:
    raise SystemExit("expected claude stage in app.txt")
path.write_text(existing.rstrip() + "\nstage=codex\n", encoding="utf-8")
print(json.dumps({"type": "thread.started", "thread_id": "thread-codex"}))
print(json.dumps({"type": "turn.completed"}))
print(json.dumps({"type": "agent_message", "message": "continued from handoff"}))
raise SystemExit(0)
