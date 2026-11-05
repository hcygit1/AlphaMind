"""FastAPI application factory."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_PROJECT_ROOT / ".env", override=False)

from server.api import (
    agent,
    automation,
    factor,
    market,
    reports,
    research,
    runtime,
    strategy,
    trading,
)
from server.core.config import get_settings
from server.db.connection import init_db
from server.db.repositories import (
    cancel_active_research_tasks,
    interrupt_stale_sync_runs,
    upsert_default_identity,
)
from server.services.agent_service import AgentService
from server.services.factor_service import FactorService
from server.services.market_service import MarketService
from server.services.research_service import ResearchService
from server.services.scheduler_service import SchedulerService
from server.services.strategy_service import StrategyService


def create_app(research_service: ResearchService | None = None) -> FastAPI:
    settings = get_settings()
    init_db(settings.database_path)
    upsert_default_identity(settings.database_path)
    cancel_active_research_tasks(settings.database_path, "服务重启，任务已中断")
    interrupt_stale_sync_runs(settings.database_path)

    app = FastAPI(title="AlphaMind Workbench API")
    app.state.database_path = settings.database_path
    app.state.research_service = research_service or ResearchService(settings.database_path)
    app.state.market_service = MarketService(settings.database_path)
    app.state.factor_service = FactorService(settings.database_path)
    app.state.strategy_service = StrategyService(settings.database_path)
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
    app.include_router(trading.router)
    app.include_router(automation.router)
    app.include_router(market.router)
    app.include_router(factor.router)
    app.include_router(strategy.router)

    scheduler = SchedulerService(settings.database_path, app.state.research_service)
    app.state.scheduler_service = scheduler
    scheduler.start()

    @app.get("/api/health")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
