from alphamind.agent_runtime.context.types import AgentContext
from alphamind.agent_runtime.router import IntentRouter
from alphamind.agent_runtime.runtime import AgentRuntime
from alphamind.agent_runtime.tools.base import ToolResult
from alphamind.agent_runtime.tools.registry import ToolRegistry


class FakeTool:
    name = "report_summary"

    def run(self, arguments, context):
        return ToolResult(
            tool_name=self.name,
            status="completed",
            content="这是报告摘要。",
            payload={"section": arguments.get("section")},
        )


def test_intent_router_detects_report_summary():
    router = IntentRouter()
    intent = router.route("总结这个报告")
    assert intent.name == "report_summary"


def test_agent_runtime_dispatches_report_summary_tool():
    registry = ToolRegistry()
    registry.register(FakeTool())
    runtime = AgentRuntime(tool_registry=registry)

    response = runtime.handle_message(
        message="总结这个报告",
        context=AgentContext(
            user_id="default_user",
            workspace_id="default_workspace",
            session_id="session_1",
            page={"page": "report_detail", "context": {"active_report_id": "report_1"}},
            report={},
            task={},
            memory={},
            recent_messages=[],
        ),
    )

    assert response.content == "这是报告摘要。"
    assert response.tool_cards[0]["type"] == "report_summary"
