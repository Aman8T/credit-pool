from __future__ import annotations

import re
from typing import Mapping

_SENSITIVE_KEY = re.compile(
    r"(key|token|secret|password|passwd|cookie|authorization|auth|credential|api[_-]?key)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"Bearer\s+\S+", re.IGNORECASE)
_SK = re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}")
_ASSIGNED = re.compile(
    r"(?P<k>(?:api[_-]?key|token|secret|password|authorization|cookie))\s*[:=]\s*(?P<v>\S+)",
    re.IGNORECASE,
)


def is_sensitive_env_key(name: str) -> bool:
    return bool(_SENSITIVE_KEY.search(name))


def redact_text(text: str) -> str:
    text = _BEARER.sub("Bearer [REDACTED]", text)
    text = _SK.sub("sk-[REDACTED]", text)
    text = _ASSIGNED.sub(lambda m: f"{m.group('k')}=[REDACTED]", text)
    return text


def redact_env(env: Mapping[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in env.items():
        out[key] = "[REDACTED]" if is_sensitive_env_key(key) else value
    return out
