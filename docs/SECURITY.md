# Security

CreditPool coordinates local subprocesses. It is not a proxy, credential vault, or limit circumvention tool.

## Boundaries

The implementation must not:

- Share or rotate multiple consumer accounts for one vendor
- Copy OAuth tokens, cookies, API keys, or vendor session files
- Expose subscription auth as an HTTP API
- Scrape private account pages
- Auto-purchase usage
- Fall back to paid APIs
- Auto-merge or auto-push
- Upload repos or logs to a CreditPool server

## Process model

- Agents and verification run as argv arrays (`subprocess.Popen`), never `shell=True`.
- Logs redact `Bearer` tokens, `sk-` prefixes, and env keys matching key/token/secret/password/cookie/authorization.
- Vendor sandboxes and permission modes are preserved; bypass flags are rejected in config.
- SIGINT is sent to the process group on timeout, then SIGTERM.

## Data

- `.creditpool.toml` has no secrets.
- `.creditpool/` is local state and is gitignored by `creditpool init`.
- Handoff packets include diffs from the worktree, not home-directory credential files.
