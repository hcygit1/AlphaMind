"""Base tool contracts for Agent Runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from alphamind.agent_runtime.context.types import AgentContext


@dataclass
class ToolResult:
    tool_name: str
    status: str
    content: str
    payload: dict[str, Any] = field(default_factory=dict)


class AgentTool(Protocol):
    name: str

    def run(self, arguments: dict[str, Any], context: AgentContext) -> ToolResult:
        ...
