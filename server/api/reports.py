"""Report API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from server.db.repositories import list_reports
from server.services.report_service import build_report_detail


router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("")
def reports(request: Request) -> list[dict]:
    return list_reports(request.app.state.database_path)


@router.get("/{report_id}")
def report_detail(report_id: str, request: Request) -> dict:
    detail = build_report_detail(request.app.state.database_path, report_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Report not found")
    return detail
