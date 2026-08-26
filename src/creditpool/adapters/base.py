from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from creditpool.config import AppConfig, resolve_bin_argv
from creditpool.models import Availability, DetectResult, ParsedRun
from creditpool.process import run_argv


@dataclass
class RunContext:
    worktree: Path
    prompt: str
    handoff_path: Path | None
    timeout_seconds: float
    stdout_path: Path
    stderr_path: Path


class AgentAdapter(ABC):
    id: str

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    @abstractmethod
    def detect(self) -> DetectResult: ...

    def availability(self) -> Availability:
        detected = self.detect()
        if not detected.installed:
            return Availability.unavailable
        return Availability.unknown

    @abstractmethod
    def build_command(self, ctx: RunContext) -> list[str]: ...

    @abstractmethod
    def parse_output(self, stdout: str, stderr: str, exit_code: int | None) -> ParsedRun: ...

    def classify_notes(self) -> str:
        return ""

    def version_argv(self) -> list[str]:
        return [*resolve_bin_argv(self.config.bin_for(self.id)), "--version"]

    def probe_version(self) -> str | None:
        from tempfile import TemporaryDirectory

        bin_argv = resolve_bin_argv(self.config.bin_for(self.id))
        detected_path = _which(bin_argv[0])
        if detected_path is None and not Path(bin_argv[0]).exists():
            return None
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "v-out.txt"
            err = Path(tmp) / "v-err.txt"
            code, timed_out, _, _ = run_argv(
                self.version_argv(),
                cwd=Path(tmp),
                stdout_path=out,
                stderr_path=err,
                timeout_seconds=15,
            )
            if timed_out or code not in (0, None):
                text = out.read_text(encoding="utf-8") + err.read_text(encoding="utf-8")
                return text.strip()[:200] or None
            return (out.read_text(encoding="utf-8") or err.read_text(encoding="utf-8")).strip()[:200]


def _which(name: str) -> str | None:
    import shutil

    path = Path(name)
    if path.is_file():
        return str(path)
    return shutil.which(name)


def detect_binary(bin_spec: str) -> DetectResult:
    path = Path(bin_spec)
    if path.suffix.lower() == ".py":
        if not path.is_file():
            return DetectResult(installed=False, notes=f"{bin_spec} not found")
        return DetectResult(installed=True, bin_path=str(path.resolve()))
    argv = resolve_bin_argv(bin_spec)
    found = _which(argv[0])
    if found is None and not Path(argv[0]).exists():
        return DetectResult(installed=False, notes=f"{argv[0]} not found on PATH")
    return DetectResult(installed=True, bin_path=found or argv[0])
