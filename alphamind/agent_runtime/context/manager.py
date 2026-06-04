"""Agent context aggregation."""

from __future__ import annotations

from alphamind.agent_runtime.context.types import AgentContext


class AgentContextManager:
    def build_context(self, session_id: str) -> AgentContext:
        return AgentContext(
            user_id="default_user",
            workspace_id="default_workspace",
            session_id=session_id,
        )
