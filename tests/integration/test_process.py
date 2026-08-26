from pathlib import Path

from creditpool.process import run_argv


def test_timeout_kills_process(tmp_path: Path) -> None:
    stdout = tmp_path / "out.txt"
    stderr = tmp_path / "err.txt"
    script = tmp_path / "sleep.py"
    script.write_text("import time; time.sleep(30)\n", encoding="utf-8")
    import sys

    code, timed_out, cancelled, _ = run_argv(
        [sys.executable, str(script)],
        cwd=tmp_path,
        stdout_path=stdout,
        stderr_path=stderr,
        timeout_seconds=1,
    )
    assert timed_out is True
    assert cancelled is False
    assert code != 0 or timed_out
