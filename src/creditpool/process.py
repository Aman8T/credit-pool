from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from creditpool.redact import redact_text


def _creationflags() -> int:
    if sys.platform == "win32":
        return getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return 0


def _kill_process_tree(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        try:
            proc.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
        except (AttributeError, OSError, ValueError):
            proc.kill()
        return
    try:
        os.killpg(proc.pid, signal.SIGINT)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.send_signal(signal.SIGINT)
        except (ProcessLookupError, OSError):
            pass
    try:
        proc.wait(timeout=3)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        proc.kill()


def run_argv(
    argv: list[str],
    *,
    cwd: Path,
    stdout_path: Path,
    stderr_path: Path,
    timeout_seconds: float,
    env: dict[str, str] | None = None,
) -> tuple[int | None, bool, bool, int]:
    """Run argv without a shell. Returns exit_code, timed_out, cancelled, duration_ms."""
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    popen_env = os.environ.copy() if env is None else dict(env)
    kwargs: dict[str, object] = {
        "cwd": str(cwd),
        "env": popen_env,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "creationflags": _creationflags(),
    }
    if sys.platform != "win32":
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(argv, **kwargs)  # noqa: S603 — argv list, never shell
    timed_out = False
    cancelled = False
    try:
        stdout_b, stderr_b = proc.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_process_tree(proc)
        stdout_b, stderr_b = proc.communicate()
    except KeyboardInterrupt:
        cancelled = True
        _kill_process_tree(proc)
        stdout_b, stderr_b = proc.communicate()
        raise
    finally:
        duration_ms = int((time.monotonic() - start) * 1000)
        stdout_text = redact_text((stdout_b or b"").decode("utf-8", errors="replace"))
        stderr_text = redact_text((stderr_b or b"").decode("utf-8", errors="replace"))
        stdout_path.write_text(stdout_text, encoding="utf-8")
        stderr_path.write_text(stderr_text, encoding="utf-8")
    return proc.returncode, timed_out, cancelled, duration_ms
