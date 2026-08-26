# CreditPool

Local-first, quota-aware task runner for developers who already pay for multiple official AI coding CLIs.

> One repository. One task queue. Every coding subscription.

CreditPool is **not** an account-sharing, credential-pooling, API-proxy, or rate-limit-bypass tool. It only coordinates official CLIs that **you** installed and authenticated (`claude`, `codex`, and optionally Cursor).

## What it does

1. You submit one repository task.
2. CreditPool creates an isolated Git branch and worktree.
3. It runs the first configured official CLI non-interactively.
4. If that CLI stops with a **recognized** usage or rate limit (or a temporary unavailable error), CreditPool writes a structured handoff packet and continues in the **same worktree** with the next CLI.
5. On success it runs your optional verification command.
6. It **never** merges, pushes, or opens a pull request.

The workflow V1 is built to prove:

**Claude Code hits a recognized limit mid-task → CreditPool keeps the edits and a handoff → Codex CLI continues → verification passes → you review the branch.**

## Non-goals

- Web dashboard, hosted service, or team pools
- Multiple consumer accounts per vendor
- Parallel agents, debates, or quality routing
- API-key fallback or provider proxies (see Claude Code Router)
- Scraping account pages, cookies, or unofficial quota APIs
- Auto-merge / auto-push / auto-PR

## Install

Python 3.11+ and Git are required.

```bash
pip install -e ".[dev]"
```

The command name is `creditpool`.

## Quick start

```bash
cd /path/to/your/git/repo
creditpool init
creditpool doctor
creditpool run "Add a --json flag to the CLI and update tests"
creditpool tasks
creditpool show <task-id>
```

Review the worktree printed at the end. Merge yourself if you want the changes.

## Configuration

`creditpool init` writes `.creditpool.toml` (safe to commit) and gitignores `.creditpool/` (ledger, logs, worktrees).

Do **not** put API keys, OAuth tokens, cookies, or vendor secrets in the config. Each vendor CLI keeps its own login.

See [docs/CONFIG.md](docs/CONFIG.md), [docs/ADAPTERS.md](docs/ADAPTERS.md), and [docs/SECURITY.md](docs/SECURITY.md).

## Quota honesty

Subscriber quota percentages are **unknown** unless a vendor CLI emits a documented machine-readable limit error. CreditPool does not scrape private APIs or treat unknown quota as zero. An installed agent with unknown quota can still be tried in configured priority order.

Automatic fallback only happens for classified `rate_limit` and `unavailable` terminations. Authentication failures, permission errors, crashes, timeouts, malformed output, and test failures are reported and **do not** rotate agents.

## Cursor CLI

Official Cursor print mode applies file writes only with `--force` / `--yolo`. V1 leaves Cursor **disabled** so CreditPool does not pass a permission-bypass flag by default. `creditpool doctor` explains this if the `agent` binary is installed.

## License

MIT
