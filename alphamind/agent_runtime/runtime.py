"""Agent Runtime orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from alphamind.agent_runtime.context.types import AgentContext
from alphamind.agent_runtime.router import IntentRouter
from alphamind.agent_runtime.tools.registry import ToolRegistry


@dataclass
class AgentResponse:
    content: str
    tool_cards: list[dict[str, Any]] = field(default_factory=list)


class AgentRuntime:
    def __init__(
        self,
        tool_registry: ToolRegistry | None = None,
        router: IntentRouter | None = None,
    ) -> None:
        self.tool_registry = tool_registry or ToolRegistry()
        self.router = router or IntentRouter()

    def handle_message(self, message: str, context: AgentContext) -> AgentResponse:
        intent = self.router.route(message)
        if intent.name == "chat":
            return AgentResponse(content="我可以帮你总结当前报告，或启动深度投研任务。")

        tool = self.tool_registry.get(intent.name)
        if tool is None:
            return AgentResponse(content=f"当前版本还没有启用 {intent.name} 工具。")

        result = tool.run(intent.arguments, context)
        return AgentResponse(
            content=result.content,
            tool_cards=[
                {
                    "type": result.tool_name,
                    "status": result.status,
                    "payload": result.payload,
                }
            ],
        )
