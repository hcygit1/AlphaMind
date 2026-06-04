"""Report API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from server.core.config import get_settings
from server.db.connection import init_db
from server.db.repositories import list_reports, upsert_default_identity
from server.services.report_service import build_report_detail


router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("")
def reports() -> list[dict]:
    settings = get_settings()
    init_db(settings.database_path)
    upsert_default_identity(settings.database_path)
    return list_reports(settings.database_path)


@router.get("/{report_id}")
def report_detail(report_id: str) -> dict:
    settings = get_settings()
    detail = build_report_detail(settings.database_path, report_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Report not found")
    return detail
