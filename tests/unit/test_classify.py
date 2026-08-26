from __future__ import annotations

from pathlib import Path

from creditpool.classify import classify
from creditpool.models import ParsedRun, Termination


def test_rate_limit_category() -> None:
    parsed = ParsedRun(error_category="rate_limit", error_message="limit")
    assert (
        classify(parsed, exit_code=1, timed_out=False, cancelled=False, stderr="")
        == Termination.rate_limit
    )


def test_auth_not_fallback() -> None:
    parsed = ParsedRun(error_category="authentication_failed")
    assert (
        classify(parsed, exit_code=1, timed_out=False, cancelled=False, stderr="")
        == Termination.auth
    )


def test_success_exit_zero() -> None:
    parsed = ParsedRun()
    assert (
        classify(parsed, exit_code=0, timed_out=False, cancelled=False, stderr="")
        == Termination.success
    )


def test_usage_text_only_on_nonzero_exit() -> None:
    parsed = ParsedRun(result_text="docs mention rate limit")
    assert (
        classify(parsed, exit_code=0, timed_out=False, cancelled=False, stderr="")
        == Termination.success
    )
    parsed2 = ParsedRun(error_message="You've hit your usage limit. Try again at 3pm")
    assert (
        classify(parsed2, exit_code=1, timed_out=False, cancelled=False, stderr="")
        == Termination.rate_limit
    )


def test_timeout_and_malformed() -> None:
    parsed = ParsedRun()
    assert (
        classify(parsed, exit_code=None, timed_out=True, cancelled=False, stderr="")
        == Termination.timeout
    )
    parsed_m = ParsedRun(malformed=True)
    assert (
        classify(parsed_m, exit_code=1, timed_out=False, cancelled=False, stderr="")
        == Termination.malformed
    )
