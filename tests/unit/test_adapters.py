from creditpool.adapters.claude import ClaudeAdapter
from creditpool.adapters.codex import CodexAdapter
from creditpool.config import AppConfig
from creditpool.models import Termination
from creditpool.classify import classify


def test_claude_stream_json_rate_limit() -> None:
    adapter = ClaudeAdapter(AppConfig())
    stdout = (
        '{"type":"error","error":"rate_limit","session_id":"abc"}\n'
        '{"type":"result","is_error":true,"result":"limited","session_id":"abc"}\n'
    )
    parsed = adapter.parse_output(stdout, "", 1)
    assert parsed.session_id == "abc"
    assert parsed.error_category == "rate_limit"
    assert (
        classify(parsed, exit_code=1, timed_out=False, cancelled=False, stderr="")
        == Termination.rate_limit
    )


def test_codex_usage_limit_object() -> None:
    adapter = CodexAdapter(AppConfig())
    stdout = (
        '{"type":"error","error":{"name":"UsageLimitReachedError","message":"limit"}}\n'
    )
    parsed = adapter.parse_output(stdout, "", 1)
    assert parsed.error_category in {"usage_limit_reached", "usagelimitreachederror"} or (
        parsed.error_category and "usage" in parsed.error_category
    )
    term = classify(parsed, exit_code=1, timed_out=False, cancelled=False, stderr="")
    assert term == Termination.rate_limit


def test_claude_build_command_uses_argv_list() -> None:
    adapter = ClaudeAdapter(AppConfig())
    from creditpool.adapters.base import RunContext
    from pathlib import Path

    ctx = RunContext(
        worktree=Path("."),
        prompt="do the thing",
        handoff_path=None,
        timeout_seconds=1,
        stdout_path=Path("o"),
        stderr_path=Path("e"),
    )
    argv = adapter.build_command(ctx)
    assert isinstance(argv, list)
    assert "-p" in argv
    assert "--dangerously-skip-permissions" not in argv
    assert argv[-1] == "do the thing"
