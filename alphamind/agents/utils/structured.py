"""Shared helpers for invoking an agent with structured output and a graceful fallback.

The Portfolio Manager, Trader, and Research Manager all follow the same
canonical pattern:

1. At agent creation, wrap the LLM with ``with_structured_output(Schema)``
   so the model returns a typed Pydantic instance. If the provider does
   not support structured output (rare; mostly older Ollama models), the
   wrap is skipped and the agent uses free-text generation instead.
2. At invocation, run the structured call and render the result back to
   markdown. If the structured call itself fails for any reason
   (malformed JSON from a weak model, transient provider issue), fall
   back to a plain ``llm.invoke`` so the pipeline never blocks.

Centralising the pattern here keeps the agent factories small and ensures
all three agents log the same warnings when fallback fires.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional, TypeVar

from pydantic import BaseModel

from alphamind.llm_clients.openai_client import DeepSeekChatOpenAI

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class _JsonModeStructuredRunnable:
    def __init__(self, structured_llm: Any, schema: type[BaseModel]):
        self.structured_llm = structured_llm
        self.schema = schema

    def invoke(self, prompt: Any) -> Any:
        return self.structured_llm.invoke(_with_json_mode_instruction(prompt, self.schema))


def _with_json_mode_instruction(prompt: Any, schema: type[BaseModel]) -> Any:
    schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    instruction = (
        "\n\nReturn only a valid JSON object matching this schema. "
        "Do not include markdown fences or explanatory text.\n"
        f"JSON schema: {schema_json}"
    )
    if isinstance(prompt, str):
        return prompt + instruction
    if isinstance(prompt, list):
        messages = []
        inserted = False
        for message in reversed(prompt):
            if (
                isinstance(message, dict)
                and message.get("role") == "user"
                and isinstance(message.get("content"), str)
            ):
                messages.append({**message, "content": message["content"] + instruction})
                inserted = True
            else:
                messages.append(message)
        messages.reverse()
        if inserted:
            return messages
    return prompt


def bind_structured(llm: Any, schema: type[T], agent_name: str) -> Optional[Any]:
    """Return ``llm.with_structured_output(schema)`` or ``None`` if unsupported.

    Logs a warning when the binding fails so the user understands the agent
    will use free-text generation for every call instead of one-shot fallback.
    """
    try:
        # The provider marker lives on the client wrapper, not on the LLM
        # instance it returns, so also match on the concrete class —
        # otherwise DeepSeek LLMs silently take the function-calling path
        # and 400 on thinking models (no tool_choice support).
        if (
            isinstance(llm, DeepSeekChatOpenAI)
            or getattr(llm, "provider", "").lower() == "deepseek"
        ):
            return _JsonModeStructuredRunnable(
                llm.with_structured_output(schema, method="json_mode"),
                schema,
            )
        return llm.with_structured_output(schema)
    except (NotImplementedError, AttributeError) as exc:
        logger.warning(
            "%s: provider does not support with_structured_output (%s); "
            "falling back to free-text generation",
            agent_name, exc,
        )
        return None


def invoke_structured_or_freetext(
    structured_llm: Optional[Any],
    plain_llm: Any,
    prompt: Any,
    render: Callable[[T], str],
    agent_name: str,
) -> str:
    """Run the structured call and render to markdown; fall back to free-text on any failure.

    ``prompt`` is whatever the underlying LLM accepts (a string for chat
    invocations, a list of message dicts for chat models that take that
    shape). The same value is forwarded to the free-text path so the
    fallback sees the same input the structured call did.
    """
    if structured_llm is not None:
        try:
            result = structured_llm.invoke(prompt)
            return render(result)
        except Exception as exc:
            logger.warning(
                "%s: structured-output invocation failed (%s); retrying once as free text",
                agent_name, exc,
            )

    response = plain_llm.invoke(prompt)
    return response.content
