from langchain_core.messages import HumanMessage, RemoveMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# Import tools from separate utility files
from alphamind.agents.utils.core_stock_tools import (
    get_stock_data
)
from alphamind.agents.utils.technical_indicators_tools import (
    get_indicators
)
from alphamind.agents.utils.fundamental_data_tools import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement
)
from alphamind.agents.utils.news_data_tools import (
    get_news,
    get_insider_transactions,
    get_global_news
)
from alphamind.agents.utils.signal_data_tools import (
    get_profit_forecast,
    get_hot_stocks,
    get_northbound_flow,
    get_concept_blocks,
    get_fund_flow,
    get_dragon_tiger_board,
    get_lockup_expiry,
    get_industry_comparison,
)


def get_language_instruction() -> str:
    """Return a prompt instruction for the configured output language.

    Returns empty string when English (default), so no extra tokens are used.
    Only applied to user-facing agents (analysts, portfolio manager).
    Internal debate agents stay in English for reasoning quality.
    """
    from alphamind.dataflows.config import get_config
    lang = get_config().get("output_language", "English")
    if lang.strip().lower() == "english":
        return ""
    return f" Write your entire response in {lang}."


def build_instrument_context(ticker: str) -> str:
    """Describe the exact instrument so agents preserve exchange-qualified tickers."""
    return (
        f"The instrument to analyze is `{ticker}`. "
        "Use this exact ticker in every tool call, report, and recommendation, "
        "preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`)."
    )


_ANALYST_SYSTEM_SKELETON = (
    "You are a helpful AI assistant, collaborating with other assistants."
    " Use the provided tools to progress towards answering the question."
    " If you are unable to fully answer, that's OK; another assistant with different tools"
    " will help where you left off. Execute what you can to make progress."
    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
    " You have access to the following tools: {tool_names}.\n{system_message}"
    "For your reference, the current date is {current_date}. {instrument_context}"
)


def build_analyst_chain(llm, tools, system_message: str, state):
    """7 个 analyst 共用的 prompt 骨架 + 工具链构造。

    仅 system_message（领域指令）各不相同，其余骨架逐字一致，
    统一到这一处避免 7 份复制粘贴漂移。
    """
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _ANALYST_SYSTEM_SKELETON),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )
    prompt = prompt.partial(system_message=system_message)
    prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
    prompt = prompt.partial(current_date=state["trade_date"])
    prompt = prompt.partial(instrument_context=build_instrument_context(state["company_of_interest"]))
    return prompt | llm.bind_tools(tools)

def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add placeholder for Anthropic compatibility"""
        messages = state["messages"]

        # Remove all messages
        removal_operations = [RemoveMessage(id=m.id) for m in messages]

        # Add a minimal placeholder message
        placeholder = HumanMessage(content="Continue")

        return {"messages": removal_operations + [placeholder]}

    return delete_messages


def wrap_analyst_node(node, report_key: str, analyst_label: str):
    """为 analyst 节点加统一异常兜底。

    LLM 超时/限流/工具循环失败时不让整条 graph.invoke 崩掉，
    而是写入降级报告，由后续质量门控与辩论链感知数据缺失。
    """
    import logging

    logger = logging.getLogger(__name__)

    def wrapped(state):
        try:
            return node(state)
        except Exception as exc:
            logger.exception("%s failed: %s", analyst_label, exc)
            fallback = (
                f"[分析失败: {analyst_label} 在本次运行中遇到错误（{type(exc).__name__}），"
                "未能生成报告。请将该维度视为数据缺失，谨慎评估整体结论。]"
            )
            return {
                "messages": [
                    HumanMessage(content=f"[{analyst_label} 执行失败: {exc}]")
                ],
                report_key: fallback,
            }

    wrapped.__name__ = getattr(node, "__name__", analyst_label)
    return wrapped


        
