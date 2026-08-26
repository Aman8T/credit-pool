from __future__ import annotations

import json

from creditpool.adapters.base import AgentAdapter, RunContext, detect_binary
from creditpool.classify import extract_error_fields
from creditpool.config import resolve_bin_argv
from creditpool.models import DetectResult, ParsedRun


def _jsonl(text: str) -> tuple[list[dict], bool]:
    events: list[dict] = []
    malformed = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            if line.startswith("{"):
                malformed = True
            continue
        if isinstance(obj, dict):
            events.append(obj)
    return events, malformed


class CodexAdapter(AgentAdapter):
    id = "codex"

    def detect(self) -> DetectResult:
        spec = self.config.bin_for(self.id)
        result = detect_binary(spec)
        if result.installed:
            result.version = self.probe_version()
        return result

    def build_command(self, ctx: RunContext) -> list[str]:
        cfg = self.config.agents.codex
        argv = [
            *resolve_bin_argv(self.config.bin_for(self.id)),
            "exec",
            "--json",
            "--sandbox",
            cfg.sandbox,
            "-c",
            f"approval_policy={cfg.approval_policy}",
            ctx.prompt,
        ]
        return argv

    def parse_output(self, stdout: str, stderr: str, exit_code: int | None) -> ParsedRun:
        events, malformed = _jsonl(stdout)
        session_id = None
        result_text = None
        for event in events:
            if event.get("type") == "thread.started":
                thread = event.get("thread_id") or event.get("id")
                if thread:
                    session_id = str(thread)
            if event.get("type") in {"agent_message", "item.completed"}:
                msg = event.get("message") or event.get("text")
                if isinstance(msg, str):
                    result_text = msg
        category, message = extract_error_fields(events, stderr)
        for event in events:
            err = event.get("error")
            if isinstance(err, dict):
                name = str(err.get("name") or err.get("type") or "")
                if "usagelimit" in name.lower().replace("_", ""):
                    category = "usage_limit_reached"
        return ParsedRun(
            events=events,
            session_id=session_id,
            result_text=result_text,
            error_category=category,
            error_message=message,
            malformed=malformed and not events,
        )
