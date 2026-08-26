from __future__ import annotations

import json
import sys
from pathlib import Path

if "--version" in sys.argv:
    print("fake-claude 0.0.1")
    raise SystemExit(0)

Path("ok.txt").write_text("ok\n", encoding="utf-8")
print(
    json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "done",
            "session_id": "sess-ok",
        }
    )
)
raise SystemExit(0)
