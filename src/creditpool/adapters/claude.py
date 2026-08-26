from __future__ import annotations

import json

from creditpool.adapters.base import AgentAdapter, RunContext, detect_binary
from creditpool.classify import extract_error_fields
from creditpool.config import resolve_bin_argv
from creditpool.models import DetectResult, ParsedRun


def _json_lines(text: str) -> tuple[list[dict], bool]:
    events: list[dict] = []
    malformed = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            if line.startswith("{") or line.startswith("["):
                malformed = True
            continue
        if isinstance(obj, dict):
            events.append(obj)
        else:
            malformed = True
    return events, malformed


class ClaudeAdapter(AgentAdapter):
    id = "claude"

    def detect(self) -> DetectResult:
        spec = self.config.bin_for(self.id)
        result = detect_binary(spec)
        if result.installed:
            result.version = self.probe_version()
        return result

    def build_command(self, ctx: RunContext) -> list[str]:
        cfg = self.config.agents.claude
        argv = [
            *resolve_bin_argv(self.config.bin_for(self.id)),
            "-p",
            "--output-format",
            "stream-json",
            "--permission-mode",
            cfg.permission_mode,
        ]
        if cfg.allowed_tools:
            argv.extend(["--allowedTools", ",".join(cfg.allowed_tools)])
        argv.append(ctx.prompt)
        return argv

    def parse_output(self, stdout: str, stderr: str, exit_code: int | None) -> ParsedRun:
        events, malformed = _json_lines(stdout)
        session_id = None
        result_text = None
        for event in events:
            if event.get("session_id") and not session_id:
                session_id = str(event["session_id"])
            if event.get("type") == "result":
                if event.get("session_id"):
                    session_id = str(event["session_id"])
                res = event.get("result")
                if isinstance(res, str):
                    result_text = res
                if event.get("is_error") and not events:
                    malformed = True
        # Whole-document JSON fallback (non-stream)
        if not events:
            stripped = stdout.strip()
            if stripped.startswith("{"):
                try:
                    obj = json.loads(stripped)
                    if isinstance(obj, dict):
                        events = [obj]
                        session_id = obj.get("session_id")
                        result_text = obj.get("result") if isinstance(obj.get("result"), str) else None
                        malformed = False
                except json.JSONDecodeError:
                    if stripped:
                        malformed = True
        category, message = extract_error_fields(events, stderr)
        for event in events:
            if event.get("type") == "error" and isinstance(event.get("error"), str):
                category = category or str(event["error"])
        return ParsedRun(
            events=events,
            session_id=session_id,
            result_text=result_text,
            error_category=category,
            error_message=message,
            malformed=malformed and not events,
        )
