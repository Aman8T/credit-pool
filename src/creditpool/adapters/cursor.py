from __future__ import annotations

from creditpool.adapters.base import AgentAdapter, RunContext, detect_binary
from creditpool.config import resolve_bin_argv
from creditpool.models import Availability, DetectResult, ParsedRun


class CursorAdapter(AgentAdapter):
    """Detect-only in V1 unless explicitly enabled with allow_force."""

    id = "cursor"

    def detect(self) -> DetectResult:
        spec = self.config.bin_for(self.id)
        result = detect_binary(spec)
        if not result.installed:
            alt = detect_binary("cursor-agent")
            if alt.installed:
                result = alt
                result.notes = "found cursor-agent"
        if result.installed:
            result.version = self.probe_version()
        result.notes = (
            (result.notes + " " if result.notes else "")
            + "V1 skips Cursor unless enabled with allow_force: official print mode "
            "applies writes only with --force/--yolo."
        )
        return result

    def availability(self) -> Availability:
        cfg = self.config.agents.cursor
        if not cfg.enabled:
            return Availability.unavailable
        if not cfg.allow_force:
            return Availability.unavailable
        return super().availability()

    def build_command(self, ctx: RunContext) -> list[str]:
        cfg = self.config.agents.cursor
        if not cfg.enabled or not cfg.allow_force:
            raise RuntimeError(
                "Cursor is disabled: official non-interactive writes require --force. "
                "Set agents.cursor.enabled and agents.cursor.allow_force to true only if you accept that flag."
            )
        return [
            *resolve_bin_argv(self.config.bin_for(self.id)),
            "-p",
            "--output-format",
            "stream-json",
            "--sandbox",
            "enabled",
            "--force",
            ctx.prompt,
        ]

    def parse_output(self, stdout: str, stderr: str, exit_code: int | None) -> ParsedRun:
        from creditpool.adapters.claude import _json_lines
        from creditpool.classify import extract_error_fields

        events, malformed = _json_lines(stdout)
        category, message = extract_error_fields(events, stderr)
        return ParsedRun(
            events=events,
            error_category=category,
            error_message=message,
            malformed=malformed and not events,
        )
