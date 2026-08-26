from __future__ import annotations

import sys
import time

if "--version" in sys.argv:
    print("fake-claude 0.0.1")
    raise SystemExit(0)

time.sleep(30)
raise SystemExit(0)
