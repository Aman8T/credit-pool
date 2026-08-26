from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskState(str, Enum):
    pending = "pending"
    running = "running"
    handing_off = "handing_off"
    verifying = "verifying"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class Availability(str, Enum):
    available = "available"
    limited = "limited"
    unknown = "unknown"
    unavailable = "unavailable"
    unauthenticated = "unauthenticated"


class Termination(str, Enum):
    success = "success"
    rate_limit = "rate_limit"
    unavailable = "unavailable"
    auth = "auth"
    permission = "permission"
    timeout = "timeout"
    crash = "crash"
    malformed = "malformed"
    unknown_error = "unknown_error"
    cancelled = "cancelled"


class DetectResult(BaseModel):
    installed: bool
    version: str | None = None
    bin_path: str | None = None
    notes: str = ""


class ParsedRun(BaseModel):
    events: list[dict[str, Any]] = Field(default_factory=list)
    session_id: str | None = None
    result_text: str | None = None
    error_category: str | None = None
    error_message: str | None = None
    malformed: bool = False
    notes: list[str] = Field(default_factory=list)


class RunResult(BaseModel):
    exit_code: int | None
    timed_out: bool = False
    cancelled: bool = False
    stdout_path: str
    stderr_path: str
    duration_ms: int
    parsed: ParsedRun
    termination: Termination
