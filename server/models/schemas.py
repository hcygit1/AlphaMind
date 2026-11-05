"""API schemas for the workbench server."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ResearchTaskCreate(BaseModel):
    ticker: str = Field(min_length=1)
    trade_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class AutomationSettingsUpdate(BaseModel):
    enabled: bool | None = None
    run_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class PageContextUpdate(BaseModel):
    session_id: str
    page: str
    context: dict[str, Any] = Field(default_factory=dict)


class AgentSessionCreate(BaseModel):
    title: str = "默认会话"


class AgentMessageCreate(BaseModel):
    content: str = Field(min_length=1)


class AgentToolCard(BaseModel):
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentMessageResponse(BaseModel):
    message_id: str
    role: Literal["assistant"]
    content: str
    tool_cards: list[AgentToolCard] = Field(default_factory=list)
