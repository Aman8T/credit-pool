from __future__ import annotations

import json
import sys

if "--version" in sys.argv:
    print("fake-claude 0.0.1")
    raise SystemExit(0)

print(
    json.dumps(
        {
            "type": "error",
            "error": "authentication_failed",
            "session_id": "sess-auth",
        }
    )
)
raise SystemExit(1)
