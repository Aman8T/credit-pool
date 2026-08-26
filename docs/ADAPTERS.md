# Adapters

Vendor-specific behavior lives in `creditpool.adapters`.

## Contract

Each adapter can:

- Detect whether the CLI is installed and report a version (`--version`)
- Report availability: `available`, `limited`, `unknown`, `unavailable`, `unauthenticated`
- Build a subprocess **argv list** (never a shell string)
- Parse structured output
- Classify termination via shared, fail-closed rules

V1 does not probe unofficial quota endpoints. Installed CLIs default to availability `unknown`.

## Claude Code

Documented invocation:

```text
claude -p --output-format stream-json --permission-mode acceptEdits --allowedTools Read,Edit,Write,Glob,Grep,Bash <prompt>
```

- Session continue (`--resume`) is not used for cross-agent handoff.
- `--bare` is not used; it skips subscription login.
- `--dangerously-skip-permissions` is not used.
- Stream-json `error` category `rate_limit` → fallback. `authentication_failed` → stop.

Quota CLI: **unknown** (no supported `claude usage --json` for subscribers).

## Codex CLI

Documented invocation:

```text
codex exec --json --sandbox workspace-write -c approval_policy=never <prompt>
```

- Default exec sandbox is read-only; coding requires `workspace-write`.
- `danger-full-access` is forbidden.
- JSONL `UsageLimitReached` / usage-limit errors → fallback when recognized.
- `codex exec resume` is not used for Claude→Codex continuation.

Quota CLI: **unknown** (no supported `codex status --json`).

## Cursor CLI

Detect-only by default. Official `-p` writes require `--force`/`--yolo`. Rate-limit frames are not typed in vendor docs. Enable only if you accept `--force`.

## Tests

CI uses fake executables under `tests/fixtures/fake_agents/`. They speak enough of the official JSON shapes for parsers and the orchestrator. They are not the vendor CLIs.
