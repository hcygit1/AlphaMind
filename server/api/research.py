"""Research task API routes."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from server.models.schemas import ResearchTaskCreate
from server.services.research_service import ResearchService


router = APIRouter(prefix="/api/research", tags=["research"])


def _service(request: Request) -> ResearchService:
    return request.app.state.research_service


@router.post("/tasks")
def create_task(payload: ResearchTaskCreate, request: Request) -> dict:
    service = _service(request)
    try:
        task = service.create_task(payload.ticker, payload.trade_date)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    service.start_task(task["id"])
    return task


@router.get("/tasks/{task_id}")
def get_task(task_id: str, request: Request) -> dict:
    task = _service(request).get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/tasks/{task_id}/events")
async def task_events(task_id: str, request: Request) -> StreamingResponse:
    service = _service(request)
    if not service.get_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_stream():
        sent = 0
        while not await request.is_disconnected():
            events = service.get_events(task_id)
            for event in events[sent:]:
                yield (
                    f"event: {event['event']}\n"
                    f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                )
            sent = len(events)
            task = service.get_task(task_id)
            if task and task.get("status") in {"completed", "failed"}:
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
