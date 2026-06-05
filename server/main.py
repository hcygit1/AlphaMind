"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.api import agent, reports, research, runtime
from server.core.config import get_settings
from server.db.connection import init_db
from server.db.repositories import upsert_default_identity
from server.services.agent_service import AgentService
from server.services.research_service import ResearchService


def create_app(research_service: ResearchService | None = None) -> FastAPI:
    settings = get_settings()
    init_db(settings.database_path)
    upsert_default_identity(settings.database_path)

    app = FastAPI(title="AlphaMind Workbench API")
    app.state.database_path = settings.database_path
    app.state.research_service = research_service or ResearchService(settings.database_path)
    app.state.agent_service = AgentService(
        settings.database_path,
        research_service=app.state.research_service,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(research.router)
    app.include_router(reports.router)
    app.include_router(agent.router)
    app.include_router(runtime.router)

    @app.get("/api/health")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
