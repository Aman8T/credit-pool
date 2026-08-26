# Configuration

CreditPool reads `.creditpool.toml` from the Git repository root.

## Example

```toml
[creditpool]
max_attempts = 3
task_timeout_seconds = 1800
artifact_dir = ".creditpool"
verification_command = []
fallback_on = ["rate_limit", "unavailable"]
branch_prefix = "creditpool"

[agents]
priority = ["claude", "codex"]

[agents.claude]
enabled = true
bin = "claude"
permission_mode = "acceptEdits"
allowed_tools = ["Read", "Edit", "Write", "Glob", "Grep", "Bash"]

[agents.codex]
enabled = true
bin = "codex"
sandbox = "workspace-write"
approval_policy = "never"

[agents.cursor]
enabled = false
bin = "agent"
allow_force = false
```

## Rules

- `verification_command` is an argv list, not a shell string. Example: `["python", "-m", "pytest", "-q"]`. Empty list skips verification.
- `fallback_on` may only contain `rate_limit` and `unavailable`.
- Codex `sandbox = "danger-full-access"` is rejected.
- Claude `permission_mode = "bypassPermissions"` is rejected.
- Cursor stays off unless `enabled` and `allow_force` are both true (not recommended).

## Environment overrides

`CREDITPOOL_CLAUDE_BIN`, `CREDITPOOL_CODEX_BIN`, and `CREDITPOOL_CURSOR_BIN` replace the configured binary (used in tests).

Python scripts as `bin` are launched with the current interpreter so Windows does not need a shebang.

## State directory

`.creditpool/` holds SQLite, attempt logs, handoff JSON, and git worktrees. `creditpool init` adds it to `.gitignore`.
