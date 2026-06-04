"""Agent session and message routes."""

from __future__ import annotations

from fastapi import APIRouter

from server.core.config import get_settings
from server.db.connection import init_db
from server.db.repositories import upsert_default_identity
from server.models.schemas import AgentMessageCreate, AgentSessionCreate
from server.services.agent_service import AgentService


router = APIRouter(prefix="/api/agent", tags=["agent"])


def _service() -> AgentService:
    settings = get_settings()
    init_db(settings.database_path)
    upsert_default_identity(settings.database_path)
    return AgentService(settings.database_path)


@router.post("/sessions")
def create_session(payload: AgentSessionCreate) -> dict:
    return _service().create_session(payload.title)


@router.get("/sessions/{session_id}")
def get_session_messages(session_id: str) -> dict:
    return {"session_id": session_id, "messages": _service().list_messages(session_id)}


@router.post("/sessions/{session_id}/messages")
def send_message(session_id: str, payload: AgentMessageCreate) -> dict:
    service = _service()
    service.add_user_message(session_id, payload.content)
    assistant = service.add_assistant_message(
        session_id,
        "我已经收到你的问题。Agent Runtime 工具调用将在后续任务接入。",
        [],
    )
    return {
        "message_id": assistant["id"],
        "role": "assistant",
        "content": assistant["content"],
        "tool_cards": [],
    }
