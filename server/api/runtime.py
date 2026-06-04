"""Runtime context API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from server.db.repositories import get_page_context, save_page_context
from server.models.schemas import PageContextUpdate


router = APIRouter(prefix="/api/runtime", tags=["runtime"])


@router.put("/page-context")
def put_page_context(payload: PageContextUpdate, request: Request) -> dict:
    if not request.app.state.agent_service.get_session(payload.session_id):
        raise HTTPException(status_code=404, detail="Agent session not found")
    return save_page_context(
        request.app.state.database_path,
        session_id=payload.session_id,
        page=payload.page,
        context=payload.context,
    )


@router.get("/page-context")
def read_page_context(session_id: str, request: Request) -> dict:
    context = get_page_context(request.app.state.database_path, session_id)
    if not context:
        raise HTTPException(status_code=404, detail="Page context not found")
    return context
