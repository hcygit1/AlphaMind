"""Agent API service wrapper."""

from __future__ import annotations

from pathlib import Path

from alphamind.agent_runtime.context.types import AgentContext
from alphamind.agent_runtime.runtime import AgentRuntime
from alphamind.agent_runtime.tools.deep_research import DeepResearchTool
from alphamind.agent_runtime.tools.registry import ToolRegistry
from alphamind.agent_runtime.tools.report_summary import ReportSummaryTool
from server.db.repositories import (
    add_agent_message,
    create_agent_session,
    get_agent_session,
    get_page_context,
    list_agent_messages,
)
from server.services.research_service import ResearchService


class AgentService:
    def __init__(self, db_path: Path | str, research_service=None):
        self.db_path = Path(db_path)
        self.research_service = research_service or ResearchService(self.db_path)

    def create_session(self, title: str) -> dict:
        return create_agent_session(self.db_path, title=title)

    def get_session(self, session_id: str) -> dict:
        return get_agent_session(self.db_path, session_id)

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

    def handle_message(self, session_id: str, content: str) -> dict:
        self.add_user_message(session_id, content)
        page_context = get_page_context(self.db_path, session_id)
        context = AgentContext(
            user_id="default_user",
            workspace_id="default_workspace",
            session_id=session_id,
            page=self._runtime_page_context(page_context),
            recent_messages=self.list_messages(session_id),
        )
        response = AgentRuntime(self._tool_registry()).handle_message(content, context)
        assistant = self.add_assistant_message(
            session_id,
            response.content,
            response.tool_cards,
        )
        return {
            "message_id": assistant["id"],
            "role": "assistant",
            "content": response.content,
            "tool_cards": response.tool_cards,
        }

    def _tool_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(ReportSummaryTool(self.db_path))
        registry.register(DeepResearchTool(self.research_service))
        return registry

    def _runtime_page_context(self, page_context: dict) -> dict:
        if not page_context:
            return {}
        context_json = page_context.get("context_json") or {}
        return {**page_context, "context": context_json}
