"""Agent API service wrapper."""

from __future__ import annotations

from pathlib import Path

from server.db.repositories import add_agent_message, create_agent_session, list_agent_messages


class AgentService:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)

    def create_session(self, title: str) -> dict:
        return create_agent_session(self.db_path, title=title)

    def list_messages(self, session_id: str) -> list[dict]:
        return list_agent_messages(self.db_path, session_id)

    def add_user_message(self, session_id: str, content: str) -> dict:
        return add_agent_message(self.db_path, session_id, "user", content)

    def add_assistant_message(
        self,
        session_id: str,
        content: str,
        tool_calls: list[dict] | None = None,
    ) -> dict:
        return add_agent_message(self.db_path, session_id, "assistant", content, tool_calls)
