from __future__ import annotations

import re
from typing import Any

from creditpool.models import ParsedRun, Termination

_USAGE = re.compile(
    r"usage[_\s-]?limit|rate[_\s-]?limit|You've hit your usage limit|quota exceeded",
    re.IGNORECASE,
)
_RESET = re.compile(r"reset|try again (at|in)|resets_at", re.IGNORECASE)
_AUTH = re.compile(
    r"not logged in|unauthenticated|authentication_failed|invalid api key|unauthorized|oauth",
    re.IGNORECASE,
)
_PERM = re.compile(
    r"permission denied|sandbox.*denied|not allowed to|approval required",
    re.IGNORECASE,
)
_UNAVAIL = re.compile(
    r"overloaded|service unavailable|temporarily unavailable|server_error",
    re.IGNORECASE,
)

_RATE_CATEGORIES = {
    "rate_limit",
    "usage_limit",
    "usage_limit_reached",
    "usagelimitreached",
    "usagelimitreachederror",
}
_UNAVAIL_CATEGORIES = {"overloaded", "server_error", "unavailable"}
_AUTH_CATEGORIES = {
    "authentication_failed",
    "oauth_org_not_allowed",
    "unauthenticated",
    "unauthorized",
}


def _as_category(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip().lower().replace("-", "_")
    if isinstance(value, dict):
        for key in ("category", "code", "type", "error", "name"):
            inner = value.get(key)
            if isinstance(inner, str):
                return inner.strip().lower().replace("-", "_")
    return None


def extract_error_fields(events: list[dict[str, Any]], stderr: str) -> tuple[str | None, str | None]:
    category = None
    message = None
    for event in events:
        if not isinstance(event, dict):
            continue
        err = event.get("error")
        cat = _as_category(err) or _as_category(event.get("category"))
        if event.get("type") in {"error", "turn.failed", "turn_failed"} and cat:
            category = cat
        if isinstance(err, str) and err:
            message = message or err
        if isinstance(err, dict):
            msg = err.get("message") or err.get("msg")
            if isinstance(msg, str):
                message = message or msg
            cat2 = _as_category(err)
            if cat2:
                category = category or cat2
        if event.get("type") == "result" and event.get("is_error"):
            res = event.get("result")
            if isinstance(res, str):
                message = message or res
    if message is None and stderr.strip():
        message = stderr.strip()[:2000]
    return category, message


def classify(
    parsed: ParsedRun,
    *,
    exit_code: int | None,
    timed_out: bool,
    cancelled: bool,
    stderr: str,
) -> Termination:
    if cancelled:
        return Termination.cancelled
    if timed_out:
        return Termination.timeout
    if parsed.malformed:
        return Termination.malformed

    category = (parsed.error_category or "").lower().replace("-", "_")
    blob = " ".join(
        part for part in (parsed.error_message, parsed.result_text, stderr) if part
    )

    if category in _AUTH_CATEGORIES:
        return Termination.auth
    if category in _RATE_CATEGORIES:
        return Termination.rate_limit
    if category in _UNAVAIL_CATEGORIES:
        return Termination.unavailable
    if category in {"invalid_request", "permission", "permission_denied"}:
        return Termination.permission

    failed = exit_code not in (0, None)
    if failed and _AUTH.search(blob):
        return Termination.auth
    # Fail closed: usage/rate phrases only count on non-zero exit (or explicit category).
    if failed and _USAGE.search(blob):
        return Termination.rate_limit
    if failed and _PERM.search(blob):
        return Termination.permission
    if failed and _UNAVAIL.search(blob):
        return Termination.unavailable

    if exit_code == 0:
        return Termination.success
    if exit_code is None:
        return Termination.crash
    if abs(exit_code) in {9, 137, 143} or exit_code < 0:
        return Termination.crash
    return Termination.unknown_error
