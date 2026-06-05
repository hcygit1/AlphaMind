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


def make_context():
    return AgentContext(
        user_id="default_user",
        workspace_id="default_workspace",
        session_id="session_1",
        page={"page": "report_detail", "context": {"active_report_id": "report_1"}},
        report={},
        task={},
        memory={},
        recent_messages=[],
    )


def test_intent_router_detects_report_summary():
    router = IntentRouter()
    intent = router.route("总结这个报告")
    assert intent.name == "report_summary"


def test_intent_router_prioritizes_deep_research_for_mixed_report_analysis():
    router = IntentRouter()
    intent = router.route("请分析一下报告")
    assert intent.name == "deep_research"
    assert intent.arguments == {"message": "请分析一下报告"}


def test_intent_router_detects_deep_research():
    router = IntentRouter()
    intent = router.route("帮我做一次深度投研")
    assert intent.name == "deep_research"
    assert intent.arguments == {"message": "帮我做一次深度投研"}


def test_agent_runtime_dispatches_report_summary_tool():
    registry = ToolRegistry()
    registry.register(FakeTool())
    runtime = AgentRuntime(tool_registry=registry)

    response = runtime.handle_message(
        message="总结这个报告",
        context=make_context(),
    )

    assert response.content == "这是报告摘要。"
    assert response.tool_cards == [
        {
            "type": "report_summary",
            "status": "completed",
            "payload": {"section": None},
        }
    ]


def test_agent_runtime_chat_fallback_returns_help_without_tool_cards():
    runtime = AgentRuntime()

    response = runtime.handle_message("你好", make_context())

    assert response.content == "我可以帮你总结当前报告，或启动深度投研任务。"
    assert response.tool_cards == []


def test_agent_runtime_unregistered_tool_fallback_returns_disabled_message():
    runtime = AgentRuntime()

    response = runtime.handle_message("帮我做一次深度投研", make_context())

    assert response.content == "当前版本还没有启用 deep_research 工具。"
    assert response.tool_cards == []
