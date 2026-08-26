from __future__ import annotations

import sys

if "--version" in sys.argv:
    print("fake-claude 0.0.1")
    raise SystemExit(0)

print("{not-json")
print("this is not structured output")
raise SystemExit(1)
