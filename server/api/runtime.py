"""Runtime context API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from server.core.config import get_settings
from server.db.connection import init_db
from server.db.repositories import get_page_context, save_page_context, upsert_default_identity
from server.models.schemas import PageContextUpdate


router = APIRouter(prefix="/api/runtime", tags=["runtime"])


@router.put("/page-context")
def put_page_context(payload: PageContextUpdate) -> dict:
    settings = get_settings()
    init_db(settings.database_path)
    upsert_default_identity(settings.database_path)
    return save_page_context(
        settings.database_path,
        session_id=payload.session_id,
        page=payload.page,
        context=payload.context,
    )


@router.get("/page-context")
def read_page_context(session_id: str) -> dict:
    settings = get_settings()
    context = get_page_context(settings.database_path, session_id)
    if not context:
        raise HTTPException(status_code=404, detail="Page context not found")
    return context
