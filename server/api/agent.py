"""Agent session and message routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from server.models.schemas import AgentMessageCreate, AgentSessionCreate
from server.services.agent_service import AgentService


router = APIRouter(prefix="/api/agent", tags=["agent"])


def _service(request: Request) -> AgentService:
    return request.app.state.agent_service


@router.post("/sessions")
def create_session(payload: AgentSessionCreate, request: Request) -> dict:
    return _service(request).create_session(payload.title)


@router.get("/sessions/{session_id}")
def get_session_messages(session_id: str, request: Request) -> dict:
    service = _service(request)
    if not service.get_session(session_id):
        raise HTTPException(status_code=404, detail="Agent session not found")
    return {"session_id": session_id, "messages": service.list_messages(session_id)}


@router.post("/sessions/{session_id}/messages")
def send_message(session_id: str, payload: AgentMessageCreate, request: Request) -> dict:
    service = _service(request)
    if not service.get_session(session_id):
        raise HTTPException(status_code=404, detail="Agent session not found")
    return service.handle_message(session_id, payload.content)
