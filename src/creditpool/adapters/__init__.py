from creditpool.adapters.claude import ClaudeAdapter
from creditpool.adapters.codex import CodexAdapter
from creditpool.adapters.cursor import CursorAdapter
from creditpool.config import AppConfig

ADAPTERS = {
    "claude": ClaudeAdapter,
    "codex": CodexAdapter,
    "cursor": CursorAdapter,
}


def get_adapter(agent_id: str, config: AppConfig):
    try:
        cls = ADAPTERS[agent_id]
    except KeyError as exc:
        raise KeyError(f"unknown agent: {agent_id}") from exc
    return cls(config)
