from __future__ import annotations

import json
import sys

if "--version" in sys.argv:
    print("fake-codex 0.0.1")
    raise SystemExit(0)

print(
    json.dumps(
        {
            "type": "error",
            "error": {
                "name": "UsageLimitReachedError",
                "message": "You've hit your usage limit. Try again at 6:00 AM",
            },
        }
    )
)
raise SystemExit(1)
