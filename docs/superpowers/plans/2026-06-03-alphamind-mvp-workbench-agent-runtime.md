# AlphaMind MVP Workbench Agent Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 1 AlphaMind Vite + FastAPI workbench with SQLite-backed deep research tasks, report browsing, current page context, and an extensible Agent Runtime skeleton.

**Architecture:** Keep `alphamind/` as the core capability layer, add `server/` as a FastAPI access layer, and add `frontend/` as the Vite React workbench. The first release reuses existing LangGraph deep research output files and stores only task/report/session/page indexes in SQLite. Agent Runtime is a thin orchestration layer with `DeepResearchTool` and `ReportSummaryTool`, while future factor/backtest/trading tools remain unregistered.

**Tech Stack:** Python 3.10+, FastAPI, uvicorn, SQLite via stdlib `sqlite3`, pytest, FastAPI TestClient/httpx, Vite, React, TypeScript, lucide-react, plain CSS.

---

## File Structure

Create:

- `server/__init__.py` - marks FastAPI package.
- `server/main.py` - app factory, CORS, router registration.
- `server/api/__init__.py` - API package marker.
- `server/api/research.py` - research task routes and SSE endpoint.
- `server/api/reports.py` - report list/detail routes.
- `server/api/agent.py` - Agent session/message routes.
- `server/api/runtime.py` - current page context routes.
- `server/core/__init__.py` - server core package marker.
- `server/core/config.py` - server settings and default user/workspace constants.
- `server/db/__init__.py` - database package marker.
- `server/db/connection.py` - SQLite connection and schema initialization.
- `server/db/repositories.py` - small repository functions for users, workspaces, tasks, reports, agent sessions/messages, page contexts.
- `server/models/__init__.py` - model package marker.
- `server/models/schemas.py` - Pydantic request/response schemas.
- `server/services/__init__.py` - service package marker.
- `server/services/report_service.py` - report indexing, loading, section extraction, summary helper.
- `server/services/research_service.py` - in-process task runner and SSE event queue.
- `server/services/agent_service.py` - bridge between API and `alphamind.agent_runtime`.
- `alphamind/agent_runtime/__init__.py` - Agent Runtime package exports.
- `alphamind/agent_runtime/runtime.py` - AgentRuntime orchestration.
- `alphamind/agent_runtime/session.py` - runtime session dataclasses.
- `alphamind/agent_runtime/router.py` - intent routing.
- `alphamind/agent_runtime/memory.py` - short-term memory abstraction.
- `alphamind/agent_runtime/context/__init__.py` - context package marker.
- `alphamind/agent_runtime/context/types.py` - AgentContext dataclasses.
- `alphamind/agent_runtime/context/manager.py` - AgentContextManager aggregator.
- `alphamind/agent_runtime/context/providers/__init__.py` - provider package marker.
- `alphamind/agent_runtime/context/providers/page.py` - page context provider.
- `alphamind/agent_runtime/context/providers/report.py` - report context provider.
- `alphamind/agent_runtime/context/providers/session.py` - session context provider.
- `alphamind/agent_runtime/context/providers/task.py` - task context provider.
- `alphamind/agent_runtime/context/providers/user.py` - user context provider.
- `alphamind/agent_runtime/context/providers/memory.py` - memory context provider.
- `alphamind/agent_runtime/tools/__init__.py` - tool package marker.
- `alphamind/agent_runtime/tools/base.py` - tool protocol and result types.
- `alphamind/agent_runtime/tools/registry.py` - ToolRegistry.
- `alphamind/agent_runtime/tools/deep_research.py` - deep research tool.
- `alphamind/agent_runtime/tools/report_summary.py` - report summary tool.
- `alphamind/agent_runtime/skills/__init__.py` - skill package marker.
- `alphamind/agent_runtime/skills/base.py` - future skill protocol.
- `alphamind/agent_runtime/skills/registry.py` - empty SkillRegistry.
- `alphamind/agent_runtime/mcp/__init__.py` - MCP package marker.
- `alphamind/agent_runtime/mcp/adapter.py` - disabled MCP adapter for Phase 1.
- `tests/server/test_db_repositories.py` - SQLite schema/repository tests.
- `tests/server/test_report_service.py` - report indexing and section extraction tests.
- `tests/server/test_research_api.py` - task route and SSE shape tests.
- `tests/server/test_agent_runtime.py` - intent routing and tool dispatch tests.
- `frontend/package.json` - frontend scripts and dependencies.
- `frontend/index.html` - Vite entry HTML.
- `frontend/tsconfig.json` - TypeScript config.
- `frontend/vite.config.ts` - Vite config.
- `frontend/src/main.tsx` - React entrypoint.
- `frontend/src/App.tsx` - layout and simple route state.
- `frontend/src/api/client.ts` - fetch helpers.
- `frontend/src/api/types.ts` - shared API types.
- `frontend/src/components/Shell.tsx` - workbench shell.
- `frontend/src/components/Sidebar.tsx` - navigation with disabled future modules.
- `frontend/src/components/AgentDrawer.tsx` - Agent small ball and drawer.
- `frontend/src/features/research/DeepResearchPage.tsx` - deep research form and progress.
- `frontend/src/features/reports/ReportsPage.tsx` - reports list/detail wrapper.
- `frontend/src/features/reports/ReportDetail.tsx` - flow Tab report viewer.
- `frontend/src/features/settings/SettingsPage.tsx` - default user/workspace and config display.
- `frontend/src/styles.css` - global responsive workbench styling.

Modify:

- `pyproject.toml` - add FastAPI backend dependencies and include `server*` package.
- `requirements.txt` - keep editable install compatibility if needed; no direct package pins because this repo currently uses `.`.
- `docs/frontend-migration.md` - add a short note that new work starts in `frontend/` and `server/`, with `web/` retained as legacy.

---

### Task 1: Add Backend Dependencies and Server Package Skeleton

**Files:**
- Modify: `pyproject.toml`
- Create: `server/__init__.py`
- Create: `server/main.py`
- Create: `server/api/__init__.py`
- Create: `server/core/__init__.py`
- Create: `server/core/config.py`
- Test: `tests/server/test_app_factory.py`

- [ ] **Step 1: Write the failing app factory test**

Create `tests/server/test_app_factory.py`:

```python
from fastapi.testclient import TestClient

from server.main import create_app


def test_create_app_exposes_healthcheck():
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/server/test_app_factory.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'server'` or `ModuleNotFoundError: No module named 'fastapi'`.

- [ ] **Step 3: Add backend dependencies**

Modify `pyproject.toml` dependencies and package discovery:

```toml
dependencies = [
    "fastapi>=0.115.0",
    "httpx>=0.27.0",
    "uvicorn[standard]>=0.30.0",
    # keep existing dependencies unchanged below this line
]

[tool.setuptools.packages.find]
include = ["alphamind*", "cli*", "web*", "server*"]
```

Keep all existing dependencies in place; insert the new three packages near the top of the dependency list without deleting existing entries.

- [ ] **Step 4: Create the server config**

Create `server/core/config.py`:

```python
"""Server settings for the AlphaMind workbench API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_USER_ID = "default_user"
DEFAULT_WORKSPACE_ID = "default_workspace"


@dataclass(frozen=True)
class ServerSettings:
    database_path: Path
    cors_origins: tuple[str, ...]


def get_settings() -> ServerSettings:
    db_path = Path(
        os.getenv(
            "ALPHAMIND_DB_PATH",
            str(Path.home() / ".alphamind" / "alphamind.sqlite3"),
        )
    )
    origins = os.getenv("ALPHAMIND_CORS_ORIGINS", "http://localhost:5173")
    return ServerSettings(
        database_path=db_path,
        cors_origins=tuple(origin.strip() for origin in origins.split(",") if origin.strip()),
    )
```

- [ ] **Step 5: Create the FastAPI app factory**

Create `server/__init__.py`:

```python
"""FastAPI backend for the AlphaMind workbench."""
```

Create `server/api/__init__.py`:

```python
"""API route modules for the AlphaMind workbench."""
```

Create `server/core/__init__.py`:

```python
"""Core server configuration."""
```

Create `server/main.py`:

```python
"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="AlphaMind Workbench API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/server/test_app_factory.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml server tests/server/test_app_factory.py
git commit -m "feat: 添加FastAPI服务骨架"
```

---

### Task 2: Add SQLite Schema and Repository Layer

**Files:**
- Create: `server/db/__init__.py`
- Create: `server/db/connection.py`
- Create: `server/db/repositories.py`
- Create: `server/models/__init__.py`
- Create: `server/models/schemas.py`
- Test: `tests/server/test_db_repositories.py`

- [ ] **Step 1: Write repository tests**

Create `tests/server/test_db_repositories.py`:

```python
from pathlib import Path

from server.db.connection import init_db
from server.db.repositories import (
    create_agent_session,
    create_research_task,
    get_page_context,
    get_research_task,
    list_active_research_tasks,
    list_reports,
    save_page_context,
    upsert_default_identity,
    upsert_report,
)


def test_repositories_persist_task_report_session_and_page_context(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)

    task = create_research_task(db_path, ticker="300750", trade_date="2026-06-03")
    loaded_task = get_research_task(db_path, task["id"])
    assert loaded_task["ticker"] == "300750"
    assert loaded_task["status"] == "pending"
    assert loaded_task["user_id"] == "default_user"
    assert loaded_task["workspace_id"] == "default_workspace"
    assert len(list_active_research_tasks(db_path)) == 1

    report = upsert_report(
        db_path,
        ticker="300750",
        trade_date="2026-06-03",
        signal="Hold",
        summary="测试摘要",
        state_path="/tmp/full_states_log_2026-06-03.json",
    )
    assert list_reports(db_path)[0]["id"] == report["id"]

    session = create_agent_session(db_path, title="默认会话")
    save_page_context(
        db_path,
        session_id=session["id"],
        page="report_detail",
        context={"active_report_id": report["id"], "active_tab": "final_decision"},
    )
    page_context = get_page_context(db_path, session["id"])
    assert page_context["page"] == "report_detail"
    assert page_context["context_json"]["active_report_id"] == report["id"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/server/test_db_repositories.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'server.db'`.

- [ ] **Step 3: Create database connection and schema**

Create `server/db/__init__.py`:

```python
"""SQLite persistence for the AlphaMind workbench."""
```

Create `server/db/connection.py`:

```python
"""SQLite connection helpers and schema setup."""

from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS research_tasks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    status TEXT NOT NULL,
    progress_stage TEXT,
    error_message TEXT,
    failed_stage TEXT,
    report_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS research_reports (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    signal TEXT NOT NULL,
    summary TEXT NOT NULL,
    state_path TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tool_calls_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES agent_sessions(id)
);

CREATE TABLE IF NOT EXISTS page_contexts (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    page TEXT NOT NULL,
    context_json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES agent_sessions(id)
);
"""


def connect(db_path: Path | str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | str) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
```

- [ ] **Step 4: Create repository functions**

Create `server/db/repositories.py` with focused helpers:

```python
"""Repository helpers for the workbench SQLite database."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from server.core.config import DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID
from server.db.connection import connect


def _uuid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _dict(row: Any) -> dict[str, Any]:
    return dict(row) if row is not None else {}


def upsert_default_identity(db_path: Path | str) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (id, display_name) VALUES (?, ?)",
            (DEFAULT_USER_ID, "Default User"),
        )
        conn.execute(
            "INSERT OR IGNORE INTO workspaces (id, user_id, name) VALUES (?, ?, ?)",
            (DEFAULT_WORKSPACE_ID, DEFAULT_USER_ID, "Default Workspace"),
        )


def create_research_task(db_path: Path | str, ticker: str, trade_date: str) -> dict[str, Any]:
    task_id = _uuid("task")
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO research_tasks
            (id, user_id, workspace_id, ticker, trade_date, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (task_id, DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID, ticker, trade_date, "pending"),
        )
        row = conn.execute("SELECT * FROM research_tasks WHERE id = ?", (task_id,)).fetchone()
    return _dict(row)


def update_research_task(db_path: Path | str, task_id: str, **fields: Any) -> dict[str, Any]:
    allowed = {"status", "progress_stage", "error_message", "failed_stage", "report_id"}
    updates = {key: value for key, value in fields.items() if key in allowed}
    if not updates:
        return get_research_task(db_path, task_id)
    assignments = ", ".join(f"{key} = ?" for key in updates)
    values = list(updates.values()) + [task_id]
    with connect(db_path) as conn:
        conn.execute(
            f"UPDATE research_tasks SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            values,
        )
        row = conn.execute("SELECT * FROM research_tasks WHERE id = ?", (task_id,)).fetchone()
    return _dict(row)


def get_research_task(db_path: Path | str, task_id: str) -> dict[str, Any]:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM research_tasks WHERE id = ?", (task_id,)).fetchone()
    return _dict(row)


def upsert_report(
    db_path: Path | str,
    ticker: str,
    trade_date: str,
    signal: str,
    summary: str,
    state_path: str,
) -> dict[str, Any]:
    report_id = _uuid("report")
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO research_reports
            (id, user_id, workspace_id, ticker, trade_date, signal, summary, state_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                DEFAULT_USER_ID,
                DEFAULT_WORKSPACE_ID,
                ticker,
                trade_date,
                signal,
                summary,
                state_path,
            ),
        )
        row = conn.execute("SELECT * FROM research_reports WHERE id = ?", (report_id,)).fetchone()
    return _dict(row)


def list_reports(db_path: Path | str) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM research_reports ORDER BY created_at DESC, trade_date DESC"
        ).fetchall()
    return [_dict(row) for row in rows]


def list_active_research_tasks(db_path: Path | str) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM research_tasks
            WHERE user_id = ? AND workspace_id = ? AND status IN ('pending', 'running')
            ORDER BY created_at ASC
            """,
            (DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID),
        ).fetchall()
    return [_dict(row) for row in rows]


def get_report(db_path: Path | str, report_id: str) -> dict[str, Any]:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM research_reports WHERE id = ?", (report_id,)).fetchone()
    return _dict(row)


def create_agent_session(db_path: Path | str, title: str = "默认会话") -> dict[str, Any]:
    session_id = _uuid("session")
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO agent_sessions (id, user_id, workspace_id, title)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID, title),
        )
        row = conn.execute("SELECT * FROM agent_sessions WHERE id = ?", (session_id,)).fetchone()
    return _dict(row)


def add_agent_message(
    db_path: Path | str,
    session_id: str,
    role: str,
    content: str,
    tool_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    message_id = _uuid("msg")
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO agent_messages (id, session_id, role, content, tool_calls_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (message_id, session_id, role, content, json.dumps(tool_calls or [], ensure_ascii=False)),
        )
        row = conn.execute("SELECT * FROM agent_messages WHERE id = ?", (message_id,)).fetchone()
    msg = _dict(row)
    msg["tool_calls_json"] = json.loads(msg["tool_calls_json"])
    return msg


def list_agent_messages(db_path: Path | str, session_id: str) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM agent_messages WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()
    messages = [_dict(row) for row in rows]
    for message in messages:
        message["tool_calls_json"] = json.loads(message["tool_calls_json"])
    return messages


def save_page_context(
    db_path: Path | str,
    session_id: str,
    page: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    context_id = _uuid("ctx")
    with connect(db_path) as conn:
        conn.execute("DELETE FROM page_contexts WHERE session_id = ?", (session_id,))
        conn.execute(
            """
            INSERT INTO page_contexts
            (id, session_id, user_id, workspace_id, page, context_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                context_id,
                session_id,
                DEFAULT_USER_ID,
                DEFAULT_WORKSPACE_ID,
                page,
                json.dumps(context, ensure_ascii=False),
            ),
        )
        row = conn.execute(
            "SELECT * FROM page_contexts WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    saved = _dict(row)
    saved["context_json"] = json.loads(saved["context_json"])
    return saved


def get_page_context(db_path: Path | str, session_id: str) -> dict[str, Any]:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM page_contexts WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    context = _dict(row)
    if context:
        context["context_json"] = json.loads(context["context_json"])
    return context
```

- [ ] **Step 5: Add shared Pydantic schemas**

Create `server/models/__init__.py`:

```python
"""Pydantic schemas for API requests and responses."""
```

Create `server/models/schemas.py`:

```python
"""API schemas for the workbench server."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ResearchTaskCreate(BaseModel):
    ticker: str = Field(min_length=1)
    trade_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


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
```

- [ ] **Step 6: Run repository tests**

Run: `pytest tests/server/test_db_repositories.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add server/db server/models tests/server/test_db_repositories.py
git commit -m "feat: 添加SQLite持久化层"
```

---

### Task 3: Implement Report Service and Legacy Log Indexing

**Files:**
- Create: `server/services/__init__.py`
- Create: `server/services/report_service.py`
- Test: `tests/server/test_report_service.py`

- [ ] **Step 1: Write report service tests**

Create `tests/server/test_report_service.py`:

```python
import json
from pathlib import Path

from server.db.connection import init_db
from server.db.repositories import upsert_default_identity
from server.services.report_service import (
    build_report_detail,
    extract_report_sections,
    index_report_file,
)


def test_index_report_file_and_build_detail(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)

    report_path = tmp_path / "300750" / "AlphaMindStrategy_logs" / "full_states_log_2026-06-03.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        json.dumps(
            {
                "company_of_interest": "300750",
                "trade_date": "2026-06-03",
                "market_report": "市场分析原文",
                "sentiment_report": "舆情分析原文",
                "news_report": "新闻分析原文",
                "fundamentals_report": "基本面分析原文",
                "policy_report": "政策分析原文",
                "hot_money_report": "资金流原文",
                "lockup_report": "解禁原文",
                "investment_debate_state": {"judge_decision": "多空结论"},
                "trader_investment_decision": "**Action**: Hold",
                "risk_debate_state": {"judge_decision": "风控结论"},
                "final_trade_decision": "**Rating**: Hold\n\n**Executive Summary**: 继续观察。",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = index_report_file(db_path, report_path)
    assert report["ticker"] == "300750"
    assert report["signal"] == "Hold"
    assert report["summary"] == "继续观察。"

    detail = build_report_detail(db_path, report["id"])
    assert detail["report"]["id"] == report["id"]
    assert detail["sections"][0]["id"] == "market"
    assert detail["sections"][-1]["id"] == "final_decision"


def test_extract_report_sections_maps_existing_state_keys():
    sections = extract_report_sections(
        {
            "market_report": "市场",
            "investment_debate_state": {"judge_decision": "辩论"},
            "final_trade_decision": "最终",
        }
    )

    section_map = {section["id"]: section["raw"] for section in sections}
    assert section_map["market"] == "市场"
    assert section_map["debate"] == "辩论"
    assert section_map["final_decision"] == "最终"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/server/test_report_service.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'server.services'`.

- [ ] **Step 3: Create the report service**

Create `server/services/__init__.py`:

```python
"""Service layer for the FastAPI backend."""
```

Create `server/services/report_service.py`:

```python
"""Report indexing and detail rendering helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from server.db.repositories import get_report, upsert_report


SECTION_DEFS = [
    ("market", "市场分析", "market_report"),
    ("sentiment", "舆情分析", "sentiment_report"),
    ("news", "新闻分析", "news_report"),
    ("fundamentals", "基本面分析", "fundamentals_report"),
    ("policy", "政策分析", "policy_report"),
    ("hot_money", "游资/资金流", "hot_money_report"),
    ("lockup", "解禁/减持", "lockup_report"),
    ("debate", "多空辩论", "investment_debate_state"),
    ("trader", "交易计划", "trader_investment_decision"),
    ("risk", "风控辩论", "risk_debate_state"),
    ("final_decision", "最终决策", "final_trade_decision"),
]


def load_state(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def extract_signal(state: dict[str, Any]) -> str:
    text = str(state.get("final_trade_decision", ""))
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    for rating in ("Buy", "Overweight", "Hold", "Underweight", "Sell"):
        if re.search(rf"\b{rating}\b", cleaned, flags=re.IGNORECASE):
            return rating
    return "N/A"


def extract_summary(state: dict[str, Any]) -> str:
    text = str(state.get("final_trade_decision", ""))
    match = re.search(r"\*\*Executive Summary\*\*:\s*(.+)", text)
    if match:
        return match.group(1).strip()
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return cleaned[:180] if cleaned else "暂无摘要"


def _raw_section(state: dict[str, Any], key: str) -> str:
    value = state.get(key, "")
    if isinstance(value, dict):
        return str(value.get("judge_decision") or value.get("history") or value)
    return str(value)


def extract_report_sections(state: dict[str, Any]) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    for section_id, title, key in SECTION_DEFS:
        raw = _raw_section(state, key)
        sections.append(
            {
                "id": section_id,
                "title": title,
                "summary": raw[:220] if raw else "暂无内容",
                "raw": raw,
            }
        )
    return sections


def index_report_file(db_path: str | Path, state_path: str | Path) -> dict[str, Any]:
    path = Path(state_path)
    state = load_state(path)
    ticker = str(state.get("company_of_interest") or path.parent.parent.name)
    trade_date = str(state.get("trade_date") or path.stem.replace("full_states_log_", ""))
    return upsert_report(
        db_path,
        ticker=ticker,
        trade_date=trade_date,
        signal=extract_signal(state),
        summary=extract_summary(state),
        state_path=str(path),
    )


def build_report_detail(db_path: str | Path, report_id: str) -> dict[str, Any]:
    report = get_report(db_path, report_id)
    if not report:
        return {}
    state = load_state(report["state_path"])
    return {
        "report": report,
        "sections": extract_report_sections(state),
        "state": state,
    }
```

- [ ] **Step 4: Run report service tests**

Run: `pytest tests/server/test_report_service.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server/services tests/server/test_report_service.py
git commit -m "feat: 添加投研报告索引服务"
```

---

### Task 4: Implement Research Task Service and SSE Event Buffer

**Files:**
- Create: `server/services/research_service.py`
- Test: `tests/server/test_research_service.py`

- [ ] **Step 1: Write service tests with a fake runner**

Create `tests/server/test_research_service.py`:

```python
from pathlib import Path

from server.db.connection import init_db
from server.db.repositories import get_research_task, upsert_default_identity
from server.services.research_service import ResearchService


class FakeRunner:
    def __call__(self, ticker: str, trade_date: str, emit):
        emit(stage="market", message="市场分析完成")
        return {
            "state_path": "/tmp/full_states_log_2026-06-03.json",
            "signal": "Hold",
            "summary": "测试摘要",
        }


def test_research_service_creates_and_runs_task(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)

    service = ResearchService(db_path=db_path, runner=FakeRunner())
    task = service.create_task("300750", "2026-06-03")

    service.run_task_sync(task["id"])

    updated = get_research_task(db_path, task["id"])
    assert updated["status"] == "completed"
    assert updated["progress_stage"] == "market"

    events = service.get_events(task["id"])
    assert events[0]["event"] == "research_progress"
    assert events[-1]["status"] == "completed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/server/test_research_service.py -v`

Expected: FAIL with `ModuleNotFoundError` or missing `ResearchService`.

- [ ] **Step 3: Create research service**

Create `server/services/research_service.py`:

```python
"""Deep research task orchestration and SSE event buffering."""

from __future__ import annotations

import threading
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from alphamind.default_config import DEFAULT_CONFIG
from alphamind.graph.trading_graph import AlphaMindGraph
from server.db.repositories import (
    create_research_task,
    get_research_task,
    list_active_research_tasks,
    update_research_task,
    upsert_report,
)


ResearchRunner = Callable[[str, str, Callable[..., None]], dict[str, Any]]


def default_runner(ticker: str, trade_date: str, emit: Callable[..., None]) -> dict[str, Any]:
    graph = AlphaMindGraph(debug=False, config=DEFAULT_CONFIG.copy())
    final_state, signal = graph.propagate(ticker, trade_date)
    safe_ticker = graph.ticker
    state_path = (
        Path(DEFAULT_CONFIG["results_dir"])
        / safe_ticker
        / "AlphaMindStrategy_logs"
        / f"full_states_log_{trade_date}.json"
    )
    emit(stage="pm", message="最终决策完成")
    return {
        "state_path": str(state_path),
        "signal": signal,
        "summary": str(final_state.get("final_trade_decision", ""))[:180],
    }


class ResearchService:
    def __init__(self, db_path: Path | str, runner: ResearchRunner = default_runner):
        self.db_path = Path(db_path)
        self.runner = runner
        self._events: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._lock = threading.Lock()

    def create_task(self, ticker: str, trade_date: str) -> dict[str, Any]:
        running = [
            task for task in self._active_tasks()
            if task.get("status") in {"pending", "running"}
        ]
        if running:
            raise RuntimeError("同一默认用户同时只能运行一个深度投研任务")
        task = create_research_task(self.db_path, ticker=ticker, trade_date=trade_date)
        self._emit(task["id"], status="pending", stage=None, message="任务已创建")
        return task

    def start_task(self, task_id: str) -> threading.Thread:
        thread = threading.Thread(target=self.run_task_sync, args=(task_id,), daemon=True)
        thread.start()
        return thread

    def run_task_sync(self, task_id: str) -> None:
        task = get_research_task(self.db_path, task_id)
        if not task:
            raise ValueError(f"Unknown task_id: {task_id}")
        update_research_task(self.db_path, task_id, status="running")
        self._emit(task_id, status="running", stage=None, message="任务开始运行")

        def emit(stage: str, message: str, payload: dict[str, Any] | None = None) -> None:
            update_research_task(self.db_path, task_id, progress_stage=stage)
            self._emit(task_id, status="running", stage=stage, message=message, payload=payload or {})

        try:
            result = self.runner(task["ticker"], task["trade_date"], emit)
            report = upsert_report(
                self.db_path,
                ticker=task["ticker"],
                trade_date=task["trade_date"],
                signal=str(result["signal"]),
                summary=str(result["summary"]),
                state_path=str(result["state_path"]),
            )
            update_research_task(
                self.db_path,
                task_id,
                status="completed",
                report_id=report["id"],
            )
            self._emit(
                task_id,
                status="completed",
                stage="completed",
                message="深度投研完成",
                payload={"report_id": report["id"]},
            )
        except Exception as exc:
            current = get_research_task(self.db_path, task_id)
            update_research_task(
                self.db_path,
                task_id,
                status="failed",
                error_message=str(exc),
                failed_stage=current.get("progress_stage"),
            )
            self._emit(task_id, status="failed", stage=current.get("progress_stage"), message=str(exc))

    def get_task(self, task_id: str) -> dict[str, Any]:
        return get_research_task(self.db_path, task_id)

    def get_events(self, task_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events.get(task_id, []))

    def _emit(
        self,
        task_id: str,
        status: str,
        stage: str | None,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        event = {
            "event": "research_progress",
            "task_id": task_id,
            "status": status,
            "stage": stage,
            "message": message,
            "payload": payload or {},
        }
        with self._lock:
            self._events[task_id].append(event)

    def _active_tasks(self) -> list[dict[str, Any]]:
        return list_active_research_tasks(self.db_path)
```

- [ ] **Step 4: Run service tests**

Run: `pytest tests/server/test_research_service.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server/services/research_service.py tests/server/test_research_service.py
git commit -m "feat: 添加深度投研任务服务"
```

---

### Task 5: Add FastAPI Routes for Research, Reports, Agent Sessions, and Page Context

**Files:**
- Modify: `server/main.py`
- Create: `server/api/research.py`
- Create: `server/api/reports.py`
- Create: `server/api/runtime.py`
- Create: `server/api/agent.py`
- Create: `server/services/agent_service.py`
- Test: `tests/server/test_research_api.py`

- [ ] **Step 1: Write API tests**

Create `tests/server/test_research_api.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient

from server.main import create_app


class FakeResearchService:
    def __init__(self):
        self.events = {}

    def create_task(self, ticker: str, trade_date: str):
        task = {
            "id": "task_1",
            "ticker": ticker,
            "trade_date": trade_date,
            "status": "pending",
            "progress_stage": None,
        }
        self.events[task["id"]] = [
            {
                "event": "research_progress",
                "task_id": task["id"],
                "status": "pending",
                "stage": None,
                "message": "任务已创建",
                "payload": {},
            }
        ]
        return task

    def start_task(self, task_id: str):
        return None

    def get_task(self, task_id: str):
        return {
            "id": task_id,
            "ticker": "300750",
            "trade_date": "2026-06-03",
            "status": "pending",
        }

    def get_events(self, task_id: str):
        return self.events.get(task_id, [])


def test_research_report_agent_and_context_routes(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setenv("ALPHAMIND_DB_PATH", str(db_path))

    app = create_app(research_service=FakeResearchService())
    client = TestClient(app)

    task_response = client.post(
        "/api/research/tasks",
        json={"ticker": "300750", "trade_date": "2026-06-03"},
    )
    assert task_response.status_code == 200
    task = task_response.json()
    assert task["ticker"] == "300750"
    assert task["status"] in {"pending", "running"}

    session_response = client.post("/api/agent/sessions", json={"title": "测试会话"})
    assert session_response.status_code == 200
    session = session_response.json()

    context_response = client.put(
        "/api/runtime/page-context",
        json={
            "session_id": session["id"],
            "page": "deep_research",
            "context": {"ticker": "300750", "trade_date": "2026-06-03"},
        },
    )
    assert context_response.status_code == 200
    assert context_response.json()["page"] == "deep_research"

    reports_response = client.get("/api/reports")
    assert reports_response.status_code == 200
    assert isinstance(reports_response.json(), list)
```

- [ ] **Step 2: Run API test to verify it fails**

Run: `pytest tests/server/test_research_api.py -v`

Expected: FAIL because route modules are missing.

- [ ] **Step 3: Create research routes**

Create `server/api/research.py`:

```python
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

    async def event_stream():
        sent = 0
        while not await request.is_disconnected():
            events = service.get_events(task_id)
            for event in events[sent:]:
                yield f"event: {event['event']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            sent = len(events)
            task = service.get_task(task_id)
            if task and task.get("status") in {"completed", "failed"}:
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 4: Create reports and runtime routes**

Create `server/api/reports.py`:

```python
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
```

Create `server/api/runtime.py`:

```python
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
```

- [ ] **Step 5: Create agent service and routes**

Create `server/services/agent_service.py`:

```python
"""Agent API service wrapper."""

from __future__ import annotations

from pathlib import Path

from server.db.repositories import (
    add_agent_message,
    create_agent_session,
    list_agent_messages,
)


class AgentService:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)

    def create_session(self, title: str) -> dict:
        return create_agent_session(self.db_path, title=title)

    def list_messages(self, session_id: str) -> list[dict]:
        return list_agent_messages(self.db_path, session_id)

    def add_user_message(self, session_id: str, content: str) -> dict:
        return add_agent_message(self.db_path, session_id, "user", content)

    def add_assistant_message(
        self,
        session_id: str,
        content: str,
        tool_calls: list[dict] | None = None,
    ) -> dict:
        return add_agent_message(self.db_path, session_id, "assistant", content, tool_calls)
```

Create `server/api/agent.py`:

```python
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
```

- [ ] **Step 6: Register routers in app factory**

Modify `server/main.py`:

```python
"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.api import agent, reports, research, runtime
from server.core.config import get_settings
from server.db.connection import init_db
from server.db.repositories import upsert_default_identity
from server.services.research_service import ResearchService


def create_app(research_service: ResearchService | None = None) -> FastAPI:
    settings = get_settings()
    init_db(settings.database_path)
    upsert_default_identity(settings.database_path)

    app = FastAPI(title="AlphaMind Workbench API")
    app.state.research_service = research_service or ResearchService(settings.database_path)

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
```

- [ ] **Step 7: Run API tests**

Run: `pytest tests/server/test_research_api.py tests/server/test_app_factory.py -v`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add server/api server/services/agent_service.py server/main.py tests/server/test_research_api.py
git commit -m "feat: 添加工作台API路由"
```

---

### Task 6: Add Agent Runtime Core and Tool Registry

**Files:**
- Create all `alphamind/agent_runtime/**` files listed in File Structure.
- Modify: `server/services/agent_service.py`
- Test: `tests/server/test_agent_runtime.py`

- [ ] **Step 1: Write Agent Runtime tests**

Create `tests/server/test_agent_runtime.py`:

```python
from alphamind.agent_runtime.context.types import AgentContext
from alphamind.agent_runtime.router import IntentRouter
from alphamind.agent_runtime.runtime import AgentRuntime
from alphamind.agent_runtime.tools.base import ToolResult
from alphamind.agent_runtime.tools.registry import ToolRegistry


class FakeTool:
    name = "report_summary"

    def run(self, arguments, context):
        return ToolResult(
            tool_name=self.name,
            status="completed",
            content="这是报告摘要。",
            payload={"section": arguments.get("section")},
        )


def test_intent_router_detects_report_summary():
    router = IntentRouter()
    intent = router.route("总结这个报告")
    assert intent.name == "report_summary"


def test_agent_runtime_dispatches_report_summary_tool():
    registry = ToolRegistry()
    registry.register(FakeTool())
    runtime = AgentRuntime(tool_registry=registry)

    response = runtime.handle_message(
        message="总结这个报告",
        context=AgentContext(
            user_id="default_user",
            workspace_id="default_workspace",
            session_id="session_1",
            page={"page": "report_detail", "context": {"active_report_id": "report_1"}},
            report={},
            task={},
            memory={},
            recent_messages=[],
        ),
    )

    assert response.content == "这是报告摘要。"
    assert response.tool_cards[0]["type"] == "report_summary"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/server/test_agent_runtime.py -v`

Expected: FAIL because `alphamind.agent_runtime` does not exist.

- [ ] **Step 3: Create context and tool types**

Create `alphamind/agent_runtime/context/types.py`:

```python
"""Agent context data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentContext:
    user_id: str
    workspace_id: str
    session_id: str
    page: dict[str, Any] = field(default_factory=dict)
    report: dict[str, Any] = field(default_factory=dict)
    task: dict[str, Any] = field(default_factory=dict)
    memory: dict[str, Any] = field(default_factory=dict)
    recent_messages: list[dict[str, Any]] = field(default_factory=list)
```

Create `alphamind/agent_runtime/tools/base.py`:

```python
"""Base tool contracts for Agent Runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from alphamind.agent_runtime.context.types import AgentContext


@dataclass
class ToolResult:
    tool_name: str
    status: str
    content: str
    payload: dict[str, Any] = field(default_factory=dict)


class AgentTool(Protocol):
    name: str

    def run(self, arguments: dict[str, Any], context: AgentContext) -> ToolResult:
        ...
```

Create `alphamind/agent_runtime/tools/registry.py`:

```python
"""Tool registry for Agent Runtime."""

from __future__ import annotations

from alphamind.agent_runtime.tools.base import AgentTool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {}

    def register(self, tool: AgentTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> AgentTool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)
```

- [ ] **Step 4: Create router and runtime**

Create `alphamind/agent_runtime/router.py`:

```python
"""Simple first-pass intent router."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Intent:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


class IntentRouter:
    def route(self, message: str) -> Intent:
        text = message.strip().lower()
        if any(keyword in text for keyword in ("总结", "报告", "最终决策", "风控")):
            return Intent(name="report_summary", arguments={})
        if any(keyword in text for keyword in ("深度分析", "投研", "分析一下")):
            return Intent(name="deep_research", arguments={"message": message})
        return Intent(name="chat", arguments={})
```

Create `alphamind/agent_runtime/runtime.py`:

```python
"""Agent Runtime orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from alphamind.agent_runtime.context.types import AgentContext
from alphamind.agent_runtime.router import IntentRouter
from alphamind.agent_runtime.tools.registry import ToolRegistry


@dataclass
class AgentResponse:
    content: str
    tool_cards: list[dict[str, Any]] = field(default_factory=list)


class AgentRuntime:
    def __init__(
        self,
        tool_registry: ToolRegistry | None = None,
        router: IntentRouter | None = None,
    ) -> None:
        self.tool_registry = tool_registry or ToolRegistry()
        self.router = router or IntentRouter()

    def handle_message(self, message: str, context: AgentContext) -> AgentResponse:
        intent = self.router.route(message)
        if intent.name == "chat":
            return AgentResponse(content="我可以帮你总结当前报告，或启动深度投研任务。")

        tool = self.tool_registry.get(intent.name)
        if tool is None:
            return AgentResponse(content=f"当前版本还没有启用 {intent.name} 工具。")

        result = tool.run(intent.arguments, context)
        return AgentResponse(
            content=result.content,
            tool_cards=[
                {
                    "type": result.tool_name,
                    "status": result.status,
                    "payload": result.payload,
                }
            ],
        )
```

- [ ] **Step 5: Create package markers and Phase 1 extension-point files**

Create minimal package files:

```python
# alphamind/agent_runtime/__init__.py
"""Extensible Agent Runtime for AlphaMind."""
```

```python
# alphamind/agent_runtime/context/__init__.py
"""Agent context aggregation."""
```

```python
# alphamind/agent_runtime/context/providers/__init__.py
"""Agent context providers."""
```

```python
# alphamind/agent_runtime/tools/__init__.py
"""Agent tools."""
```

```python
# alphamind/agent_runtime/skills/__init__.py
"""Future Agent skills."""
```

```python
# alphamind/agent_runtime/mcp/__init__.py
"""Future MCP adapter package."""
```

Create `alphamind/agent_runtime/skills/base.py`:

```python
"""Future skill protocol."""

from __future__ import annotations

from typing import Protocol


class AgentSkill(Protocol):
    name: str
```

Create `alphamind/agent_runtime/skills/registry.py`:

```python
"""Registry for future multi-tool skills."""

class SkillRegistry:
    def __init__(self) -> None:
        self._skills = {}
```

Create `alphamind/agent_runtime/mcp/adapter.py`:

```python
    """Disabled MCP adapter.

This adapter intentionally has no runtime behavior in Phase 1.
"""


class MCPAdapter:
    enabled = False
```

Create provider files with simple classes returning empty dictionaries:

```python
# alphamind/agent_runtime/context/providers/page.py
class PageContextProvider:
    def get(self) -> dict:
        return {}
```

Create `alphamind/agent_runtime/context/providers/report.py`:

```python
class ReportContextProvider:
    def get(self) -> dict:
        return {}
```

Create `alphamind/agent_runtime/context/providers/session.py`:

```python
class SessionContextProvider:
    def get(self) -> dict:
        return {}
```

Create `alphamind/agent_runtime/context/providers/task.py`:

```python
class TaskContextProvider:
    def get(self) -> dict:
        return {}
```

Create `alphamind/agent_runtime/context/providers/user.py`:

```python
class UserContextProvider:
    def get(self) -> dict:
        return {}
```

Create `alphamind/agent_runtime/context/providers/memory.py`:

```python
class MemoryContextProvider:
    def get(self) -> dict:
        return {}
```

Create `alphamind/agent_runtime/context/manager.py`:

```python
"""Agent context aggregation."""

from __future__ import annotations

from alphamind.agent_runtime.context.types import AgentContext


class AgentContextManager:
    def build_context(self, session_id: str) -> AgentContext:
        return AgentContext(
            user_id="default_user",
            workspace_id="default_workspace",
            session_id=session_id,
        )
```

Create `alphamind/agent_runtime/memory.py`:

```python
"""Short-term memory interface for Phase 1."""


class ShortTermMemory:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
```

Create `alphamind/agent_runtime/session.py`:

```python
"""Agent session data structures."""

from dataclasses import dataclass


@dataclass
class AgentSession:
    id: str
    user_id: str
    workspace_id: str
```

- [ ] **Step 6: Run Agent Runtime tests**

Run: `pytest tests/server/test_agent_runtime.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add alphamind/agent_runtime tests/server/test_agent_runtime.py
git commit -m "feat: 添加Agent Runtime基础接口"
```

---

### Task 7: Wire ReportSummaryTool and DeepResearchTool into Agent Service

**Files:**
- Create: `alphamind/agent_runtime/tools/report_summary.py`
- Create: `alphamind/agent_runtime/tools/deep_research.py`
- Modify: `server/services/agent_service.py`
- Test: `tests/server/test_agent_tools.py`

- [ ] **Step 1: Write tool tests**

Create `tests/server/test_agent_tools.py`:

```python
from pathlib import Path

from alphamind.agent_runtime.context.types import AgentContext
from alphamind.agent_runtime.tools.deep_research import DeepResearchTool
from alphamind.agent_runtime.tools.report_summary import ReportSummaryTool
from server.db.connection import init_db
from server.db.repositories import upsert_default_identity, upsert_report


class FakeResearchService:
    def create_task(self, ticker: str, trade_date: str):
        return {"id": "task_1", "ticker": ticker, "trade_date": trade_date, "status": "pending"}

    def start_task(self, task_id: str):
        return None


def test_report_summary_tool_reads_current_report(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    state_path = tmp_path / "state.json"
    state_path.write_text('{"final_trade_decision":"**Rating**: Hold"}', encoding="utf-8")
    init_db(db_path)
    upsert_default_identity(db_path)
    report = upsert_report(db_path, "300750", "2026-06-03", "Hold", "摘要", str(state_path))

    tool = ReportSummaryTool(db_path)
    result = tool.run(
        {},
        AgentContext(
            user_id="default_user",
            workspace_id="default_workspace",
            session_id="session_1",
            page={"context": {"active_report_id": report["id"]}},
        ),
    )

    assert result.status == "completed"
    assert "摘要" in result.content


def test_deep_research_tool_creates_task():
    tool = DeepResearchTool(FakeResearchService())
    result = tool.run(
        {"ticker": "300750", "trade_date": "2026-06-03"},
        AgentContext("default_user", "default_workspace", "session_1"),
    )

    assert result.status == "accepted"
    assert result.payload["task_id"] == "task_1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/server/test_agent_tools.py -v`

Expected: FAIL because tools do not exist.

- [ ] **Step 3: Implement ReportSummaryTool**

Create `alphamind/agent_runtime/tools/report_summary.py`:

```python
"""Report summary tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alphamind.agent_runtime.context.types import AgentContext
from alphamind.agent_runtime.tools.base import ToolResult
from server.db.repositories import get_report


class ReportSummaryTool:
    name = "report_summary"

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)

    def run(self, arguments: dict[str, Any], context: AgentContext) -> ToolResult:
        report_id = (
            arguments.get("report_id")
            or context.page.get("context", {}).get("active_report_id")
        )
        if not report_id:
            return ToolResult(
                tool_name=self.name,
                status="failed",
                content="当前页面没有可总结的报告。请先打开一个报告。",
            )
        report = get_report(self.db_path, report_id)
        if not report:
            return ToolResult(
                tool_name=self.name,
                status="failed",
                content="没有找到对应报告。",
                payload={"report_id": report_id},
            )
        content = (
            f"{report['ticker']} 在 {report['trade_date']} 的最终信号是 "
            f"{report['signal']}。摘要：{report['summary']}"
        )
        return ToolResult(
            tool_name=self.name,
            status="completed",
            content=content,
            payload={"report_id": report_id},
        )
```

- [ ] **Step 4: Implement DeepResearchTool**

Create `alphamind/agent_runtime/tools/deep_research.py`:

```python
"""Deep research task creation tool."""

from __future__ import annotations

from typing import Any

from alphamind.agent_runtime.context.types import AgentContext
from alphamind.agent_runtime.tools.base import ToolResult


class DeepResearchTool:
    name = "deep_research"

    def __init__(self, research_service):
        self.research_service = research_service

    def run(self, arguments: dict[str, Any], context: AgentContext) -> ToolResult:
        ticker = arguments.get("ticker") or context.page.get("context", {}).get("ticker")
        trade_date = arguments.get("trade_date") or context.page.get("context", {}).get("trade_date")
        if not ticker or not trade_date:
            return ToolResult(
                tool_name=self.name,
                status="failed",
                content="请提供股票代码和分析日期。",
            )
        task = self.research_service.create_task(ticker, trade_date)
        self.research_service.start_task(task["id"])
        return ToolResult(
            tool_name=self.name,
            status="accepted",
            content=f"已创建 {ticker} 在 {trade_date} 的深度投研任务。",
            payload={"task_id": task["id"], "ticker": ticker, "trade_date": trade_date},
        )
```

- [ ] **Step 5: Wire AgentRuntime in AgentService**

Modify `server/services/agent_service.py` so `send_message` can call runtime:

```python
from alphamind.agent_runtime.context.types import AgentContext
from alphamind.agent_runtime.runtime import AgentRuntime
from alphamind.agent_runtime.tools.deep_research import DeepResearchTool
from alphamind.agent_runtime.tools.registry import ToolRegistry
from alphamind.agent_runtime.tools.report_summary import ReportSummaryTool
from server.db.repositories import get_page_context
from server.services.research_service import ResearchService


    def handle_message(self, session_id: str, content: str) -> dict:
        self.add_user_message(session_id, content)
        registry = ToolRegistry()
        registry.register(ReportSummaryTool(self.db_path))
        registry.register(DeepResearchTool(ResearchService(self.db_path)))
        page_context = get_page_context(self.db_path, session_id)
        context = AgentContext(
            user_id="default_user",
            workspace_id="default_workspace",
            session_id=session_id,
            page=page_context,
            recent_messages=self.list_messages(session_id),
        )
        response = AgentRuntime(registry).handle_message(content, context)
        assistant = self.add_assistant_message(
            session_id,
            response.content,
            response.tool_cards,
        )
        return {
            "message_id": assistant["id"],
            "role": "assistant",
            "content": response.content,
            "tool_cards": response.tool_cards,
        }
```

Then modify `server/api/agent.py` `send_message` to call:

```python
return _service().handle_message(session_id, payload.content)
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/server/test_agent_tools.py tests/server/test_agent_runtime.py tests/server/test_research_api.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add alphamind/agent_runtime/tools server/services/agent_service.py server/api/agent.py tests/server/test_agent_tools.py
git commit -m "feat: 接入Agent投研工具"
```

---

### Task 8: Scaffold Vite React Workbench Shell

**Files:**
- Create all `frontend/` files listed in File Structure except feature pages can start as simple shells.

- [ ] **Step 1: Create frontend package metadata**

Create `frontend/package.json`:

```json
{
  "name": "alphamind-workbench",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "tsc && vite build",
    "preview": "vite preview --host 127.0.0.1"
  },
  "dependencies": {
    "lucide-react": "^0.468.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.6.3",
    "vite": "^5.4.11"
  }
}
```

- [ ] **Step 2: Create Vite config and entry files**

Create `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["DOM", "DOM.Iterable", "ES2020"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src"],
  "references": []
}
```

Create `frontend/vite.config.ts`:

```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173
  }
});
```

Create `frontend/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>AlphaMind Workbench</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 3: Create shell components**

Create `frontend/src/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

Create `frontend/src/App.tsx`:

```tsx
import { useState } from "react";
import { Shell } from "./components/Shell";
import { DeepResearchPage } from "./features/research/DeepResearchPage";
import { ReportsPage } from "./features/reports/ReportsPage";
import { SettingsPage } from "./features/settings/SettingsPage";

export type RouteKey = "deep-research" | "reports" | "settings";

export function App() {
  const [route, setRoute] = useState<RouteKey>("deep-research");

  return (
    <Shell route={route} onRouteChange={setRoute}>
      {route === "deep-research" && <DeepResearchPage />}
      {route === "reports" && <ReportsPage />}
      {route === "settings" && <SettingsPage />}
    </Shell>
  );
}
```

Create `frontend/src/components/Shell.tsx`:

```tsx
import type { PropsWithChildren } from "react";
import type { RouteKey } from "../App";
import { AgentDrawer } from "./AgentDrawer";
import { Sidebar } from "./Sidebar";

type ShellProps = PropsWithChildren<{
  route: RouteKey;
  onRouteChange: (route: RouteKey) => void;
}>;

export function Shell({ children, route, onRouteChange }: ShellProps) {
  return (
    <div className="app-shell">
      <Sidebar route={route} onRouteChange={onRouteChange} />
      <main className="workspace">{children}</main>
      <AgentDrawer />
    </div>
  );
}
```

Create `frontend/src/components/Sidebar.tsx`:

```tsx
import { BarChart3, Bot, ClipboardList, FileText, FlaskConical, LineChart, Settings, WalletCards } from "lucide-react";
import type { RouteKey } from "../App";

type Item =
  | { label: string; route: RouteKey; disabled?: false; icon: JSX.Element }
  | { label: string; disabled: true; icon: JSX.Element };

const items: Item[] = [
  { label: "Deep Research", route: "deep-research", icon: <Bot size={18} /> },
  { label: "Reports", route: "reports", icon: <FileText size={18} /> },
  { label: "Factor Lab", disabled: true, icon: <FlaskConical size={18} /> },
  { label: "Strategy Lab", disabled: true, icon: <LineChart size={18} /> },
  { label: "Paper Trading", disabled: true, icon: <WalletCards size={18} /> },
  { label: "Orders & Positions", disabled: true, icon: <ClipboardList size={18} /> },
  { label: "Review & Analytics", disabled: true, icon: <BarChart3 size={18} /> },
  { label: "Settings", route: "settings", icon: <Settings size={18} /> }
];

export function Sidebar({ route, onRouteChange }: { route: RouteKey; onRouteChange: (route: RouteKey) => void }) {
  return (
    <aside className="sidebar">
      <div className="brand">AlphaMind</div>
      <nav>
        {items.map((item) => (
          <button
            key={item.label}
            className={"nav-item " + (!item.disabled && item.route === route ? "active" : "")}
            disabled={item.disabled}
            onClick={() => !item.disabled && onRouteChange(item.route)}
            title={item.disabled ? "Coming Soon" : item.label}
          >
            {item.icon}
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 4: Create initial pages and styles**

Create `frontend/src/features/research/DeepResearchPage.tsx`:

```tsx
export function DeepResearchPage() {
  return (
    <section className="page">
      <h1>Deep Research</h1>
      <p>启动 AlphaMind 深度投研任务。</p>
    </section>
  );
}
```

Create `frontend/src/features/reports/ReportsPage.tsx`:

```tsx
export function ReportsPage() {
  return (
    <section className="page">
      <h1>Reports</h1>
      <p>查看历史深度投研报告。</p>
    </section>
  );
}
```

Create `frontend/src/features/settings/SettingsPage.tsx`:

```tsx
export function SettingsPage() {
  return (
    <section className="page">
      <h1>Settings</h1>
      <dl className="settings-list">
        <dt>User</dt>
        <dd>default_user</dd>
        <dt>Workspace</dt>
        <dd>default_workspace</dd>
      </dl>
    </section>
  );
}
```

Create `frontend/src/components/AgentDrawer.tsx`:

```tsx
import { Bot, X } from "lucide-react";
import { useState } from "react";

export function AgentDrawer() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button className="agent-orb" onClick={() => setOpen(true)} aria-label="Open Agent">
        <Bot size={24} />
      </button>
      {open && (
        <aside className="agent-drawer">
          <header>
            <div>
              <strong>AlphaMind Agent</strong>
              <span>当前版本支持报告总结和深度投研。</span>
            </div>
            <button onClick={() => setOpen(false)} aria-label="Close Agent">
              <X size={18} />
            </button>
          </header>
          <div className="agent-messages">
            <div className="assistant-message">我可以帮你总结当前报告，或启动深度投研任务。</div>
          </div>
          <form className="agent-input">
            <input placeholder="输入问题..." />
            <button type="submit">发送</button>
          </form>
        </aside>
      )}
    </>
  );
}
```

Create `frontend/src/styles.css` with restrained workbench styling:

```css
* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #f6f7f9;
  color: #17202a;
}

button,
input {
  font: inherit;
}

.app-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 248px minmax(0, 1fr);
}

.sidebar {
  background: #111827;
  color: #f9fafb;
  padding: 20px 14px;
}

.brand {
  font-size: 22px;
  font-weight: 800;
  margin: 0 8px 22px;
}

.nav-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  border: 0;
  border-radius: 8px;
  padding: 10px 12px;
  color: #d1d5db;
  background: transparent;
  cursor: pointer;
}

.nav-item.active {
  background: #243244;
  color: white;
}

.nav-item:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.workspace {
  padding: 28px;
  min-width: 0;
}

.page {
  max-width: 1180px;
}

.settings-list {
  display: grid;
  grid-template-columns: 160px 1fr;
  gap: 12px;
}

.agent-orb {
  position: fixed;
  right: 24px;
  bottom: 24px;
  width: 56px;
  height: 56px;
  border: 0;
  border-radius: 50%;
  background: #2563eb;
  color: white;
  display: grid;
  place-items: center;
  box-shadow: 0 10px 30px rgba(37, 99, 235, 0.28);
  cursor: pointer;
}

.agent-drawer {
  position: fixed;
  right: 0;
  top: 0;
  bottom: 0;
  width: min(440px, 100vw);
  background: white;
  border-left: 1px solid #e5e7eb;
  box-shadow: -16px 0 40px rgba(15, 23, 42, 0.12);
  display: grid;
  grid-template-rows: auto 1fr auto;
}

.agent-drawer header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 18px;
  border-bottom: 1px solid #e5e7eb;
}

.agent-drawer header span {
  display: block;
  margin-top: 4px;
  color: #64748b;
  font-size: 13px;
}

.agent-messages {
  padding: 18px;
  overflow: auto;
}

.assistant-message {
  background: #f1f5f9;
  border-radius: 8px;
  padding: 12px;
}

.agent-input {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  padding: 14px;
  border-top: 1px solid #e5e7eb;
}

.agent-input input {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 10px 12px;
}

.agent-input button {
  border: 0;
  border-radius: 8px;
  padding: 10px 14px;
  background: #2563eb;
  color: white;
}
```

- [ ] **Step 5: Build frontend**

Run:

```bash
cd frontend
npm install
npm run build
```

Expected: TypeScript build and Vite production build complete without errors.

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "feat: 添加Vite工作台前端骨架"
```

---

### Task 9: Connect Frontend to Research and Reports APIs

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/types.ts`
- Modify: `frontend/src/features/research/DeepResearchPage.tsx`
- Modify: `frontend/src/features/reports/ReportsPage.tsx`
- Create: `frontend/src/features/reports/ReportDetail.tsx`

- [ ] **Step 1: Add API types and client helpers**

Create `frontend/src/api/types.ts`:

```ts
export type ResearchTask = {
  id: string;
  ticker: string;
  trade_date: string;
  status: "pending" | "running" | "completed" | "failed";
  progress_stage?: string | null;
  report_id?: string | null;
  error_message?: string | null;
};

export type ReportSummary = {
  id: string;
  ticker: string;
  trade_date: string;
  signal: string;
  summary: string;
  state_path: string;
  created_at: string;
};

export type ReportSection = {
  id: string;
  title: string;
  summary: string;
  raw: string;
};

export type ReportDetailResponse = {
  report: ReportSummary;
  sections: ReportSection[];
};
```

Create `frontend/src/api/client.ts`:

```ts
import type { ReportDetailResponse, ReportSummary, ResearchTask } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export function createResearchTask(ticker: string, tradeDate: string) {
  return request<ResearchTask>("/api/research/tasks", {
    method: "POST",
    body: JSON.stringify({ ticker, trade_date: tradeDate })
  });
}

export function listReports() {
  return request<ReportSummary[]>("/api/reports");
}

export function getReport(reportId: string) {
  return request<ReportDetailResponse>(`/api/reports/${reportId}`);
}

export function researchEventsUrl(taskId: string) {
  return `${API_BASE}/api/research/tasks/${taskId}/events`;
}
```

- [ ] **Step 2: Implement DeepResearchPage form and SSE status**

Replace `frontend/src/features/research/DeepResearchPage.tsx`:

```tsx
import { FormEvent, useState } from "react";
import { createResearchTask, researchEventsUrl } from "../../api/client";
import type { ResearchTask } from "../../api/types";

export function DeepResearchPage() {
  const [ticker, setTicker] = useState("300750");
  const [tradeDate, setTradeDate] = useState(new Date().toISOString().slice(0, 10));
  const [task, setTask] = useState<ResearchTask | null>(null);
  const [events, setEvents] = useState<string[]>([]);
  const [error, setError] = useState("");

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setEvents([]);
    try {
      const created = await createResearchTask(ticker, tradeDate);
      setTask(created);
      const stream = new EventSource(researchEventsUrl(created.id));
      stream.addEventListener("research_progress", (message) => {
        const payload = JSON.parse((message as MessageEvent).data);
        setEvents((current) => [...current, payload.message]);
        setTask((current) =>
          current
            ? {
                ...current,
                status: payload.status,
                progress_stage: payload.stage,
                report_id: payload.payload?.report_id ?? current.report_id
              }
            : current
        );
        if (payload.status === "completed" || payload.status === "failed") {
          stream.close();
        }
      });
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }

  return (
    <section className="page">
      <h1>Deep Research</h1>
      <form className="panel-form" onSubmit={onSubmit}>
        <label>
          股票代码
          <input value={ticker} onChange={(event) => setTicker(event.target.value)} />
        </label>
        <label>
          分析日期
          <input type="date" value={tradeDate} onChange={(event) => setTradeDate(event.target.value)} />
        </label>
        <button type="submit">启动深度投研</button>
      </form>

      {error && <div className="error-box">{error}</div>}
      {task && (
        <section className="status-panel">
          <h2>任务状态</h2>
          <p>{task.status} · {task.progress_stage ?? "等待阶段更新"}</p>
          {task.report_id && <p>报告 ID：{task.report_id}</p>}
          <ul>{events.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul>
        </section>
      )}
    </section>
  );
}
```

- [ ] **Step 3: Implement report list and detail components**

Replace `frontend/src/features/reports/ReportsPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { getReport, listReports } from "../../api/client";
import type { ReportDetailResponse, ReportSummary } from "../../api/types";
import { ReportDetail } from "./ReportDetail";

export function ReportsPage() {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [detail, setDetail] = useState<ReportDetailResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    listReports().then(setReports).catch((exc) => setError(String(exc)));
  }, []);

  async function openReport(report: ReportSummary) {
    const loaded = await getReport(report.id);
    setDetail(loaded);
  }

  return (
    <section className="page report-layout">
      <div>
        <h1>Reports</h1>
        {error && <div className="error-box">{error}</div>}
        <div className="report-list">
          {reports.map((report) => (
            <button key={report.id} onClick={() => openReport(report)}>
              <strong>{report.ticker}</strong>
              <span>{report.trade_date} · {report.signal}</span>
            </button>
          ))}
        </div>
      </div>
      {detail && <ReportDetail detail={detail} />}
    </section>
  );
}
```

Create `frontend/src/features/reports/ReportDetail.tsx`:

```tsx
import { useState } from "react";
import type { ReportDetailResponse } from "../../api/types";

export function ReportDetail({ detail }: { detail: ReportDetailResponse }) {
  const [activeTab, setActiveTab] = useState(detail.sections[0]?.id ?? "");
  const active = detail.sections.find((section) => section.id === activeTab) ?? detail.sections[0];

  return (
    <article className="report-detail">
      <header>
        <h2>{detail.report.ticker}</h2>
        <span>{detail.report.trade_date} · {detail.report.signal}</span>
      </header>
      <div className="tab-row">
        {detail.sections.map((section) => (
          <button
            key={section.id}
            className={section.id === activeTab ? "active" : ""}
            onClick={() => setActiveTab(section.id)}
          >
            {section.title}
          </button>
        ))}
      </div>
      {active && (
        <section className="report-section">
          <h3>{active.title}</h3>
          <p>{active.summary}</p>
          <details open={active.id === "final_decision"}>
            <summary>查看原文</summary>
            <pre>{active.raw}</pre>
          </details>
        </section>
      )}
    </article>
  );
}
```

- [ ] **Step 4: Add CSS for forms and report tabs**

Append to `frontend/src/styles.css`:

```css
.panel-form {
  display: grid;
  grid-template-columns: minmax(180px, 240px) minmax(180px, 240px) auto;
  gap: 14px;
  align-items: end;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 18px;
}

.panel-form label {
  display: grid;
  gap: 6px;
  color: #475569;
  font-size: 14px;
}

.panel-form input {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 10px;
}

.panel-form button,
.report-list button,
.tab-row button {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 10px 12px;
  background: white;
  cursor: pointer;
}

.panel-form button {
  background: #2563eb;
  color: white;
  border-color: #2563eb;
}

.status-panel,
.report-detail {
  margin-top: 18px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 18px;
}

.error-box {
  margin-top: 12px;
  color: #b91c1c;
}

.report-layout {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 20px;
}

.report-list {
  display: grid;
  gap: 10px;
}

.report-list button {
  display: grid;
  gap: 4px;
  text-align: left;
}

.report-list span {
  color: #64748b;
}

.tab-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 16px 0;
}

.tab-row button.active {
  background: #e0ecff;
  border-color: #2563eb;
  color: #1d4ed8;
}

.report-section pre {
  white-space: pre-wrap;
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 8px;
  padding: 14px;
  overflow: auto;
}
```

- [ ] **Step 5: Build frontend**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat: 接入投研和报告前端页面"
```

---

### Task 10: Connect Agent Drawer to Agent and Page Context APIs

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/components/AgentDrawer.tsx`
- Modify: `frontend/src/features/research/DeepResearchPage.tsx`
- Modify: `frontend/src/features/reports/ReportDetail.tsx`

- [ ] **Step 1: Add Agent and page context client methods**

Modify `frontend/src/api/types.ts`:

```ts
export type AgentSession = {
  id: string;
  title: string;
};

export type AgentResponse = {
  message_id: string;
  role: "assistant";
  content: string;
  tool_cards: Array<{ type: string; status?: string; payload: Record<string, unknown> }>;
};
```

Modify `frontend/src/api/client.ts`:

```ts
import type { AgentResponse, AgentSession } from "./types";

export function createAgentSession(title = "默认会话") {
  return request<AgentSession>("/api/agent/sessions", {
    method: "POST",
    body: JSON.stringify({ title })
  });
}

export function sendAgentMessage(sessionId: string, content: string) {
  return request<AgentResponse>(`/api/agent/sessions/${sessionId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content })
  });
}

export function savePageContext(sessionId: string, page: string, context: Record<string, unknown>) {
  return request("/api/runtime/page-context", {
    method: "PUT",
    body: JSON.stringify({ session_id: sessionId, page, context })
  });
}
```

- [ ] **Step 2: Implement AgentDrawer message flow**

Replace `frontend/src/components/AgentDrawer.tsx`:

```tsx
import { Bot, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { createAgentSession, sendAgentMessage } from "../api/client";

type Message = { role: "user" | "assistant"; content: string };

export function AgentDrawer() {
  const [open, setOpen] = useState(false);
  const [sessionId, setSessionId] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "我可以帮你总结当前报告，或启动深度投研任务。" }
  ]);
  const [input, setInput] = useState("");

  useEffect(() => {
    createAgentSession().then((session) => {
      setSessionId(session.id);
      window.localStorage.setItem("alphamind_session_id", session.id);
    });
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!input.trim() || !sessionId) return;
    const content = input.trim();
    setMessages((current) => [...current, { role: "user", content }]);
    setInput("");
    const response = await sendAgentMessage(sessionId, content);
    setMessages((current) => [...current, { role: "assistant", content: response.content }]);
  }

  return (
    <>
      <button className="agent-orb" onClick={() => setOpen(true)} aria-label="Open Agent">
        <Bot size={24} />
      </button>
      {open && (
        <aside className="agent-drawer">
          <header>
            <div>
              <strong>AlphaMind Agent</strong>
              <span>当前版本支持报告总结和深度投研。</span>
            </div>
            <button onClick={() => setOpen(false)} aria-label="Close Agent">
              <X size={18} />
            </button>
          </header>
          <div className="agent-messages">
            {messages.map((message, index) => (
              <div key={index} className={message.role === "assistant" ? "assistant-message" : "user-message"}>
                {message.content}
              </div>
            ))}
          </div>
          <form className="agent-input" onSubmit={onSubmit}>
            <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="输入问题..." />
            <button type="submit">发送</button>
          </form>
        </aside>
      )}
    </>
  );
}
```

- [ ] **Step 3: Save current page context from pages**

Modify `DeepResearchPage.tsx` to call `savePageContext` after session exists:

```tsx
import { savePageContext } from "../../api/client";

function currentSessionId() {
  return window.localStorage.getItem("alphamind_session_id");
}

// inside component, after ticker/tradeDate state:
useEffect(() => {
  const sessionId = currentSessionId();
  if (sessionId) {
    savePageContext(sessionId, "deep_research", { ticker, trade_date: tradeDate });
  }
}, [ticker, tradeDate]);
```

Modify `ReportDetail.tsx` to save active report context:

```tsx
import { useEffect, useState } from "react";
import { savePageContext } from "../../api/client";

useEffect(() => {
  const sessionId = window.localStorage.getItem("alphamind_session_id");
  if (sessionId) {
    savePageContext(sessionId, "report_detail", {
      active_report_id: detail.report.id,
      active_tab: activeTab,
      ticker: detail.report.ticker,
      trade_date: detail.report.trade_date,
      signal: detail.report.signal
    });
  }
}, [activeTab, detail.report.id, detail.report.signal, detail.report.ticker, detail.report.trade_date]);
```

- [ ] **Step 4: Add user message styling**

Append to `frontend/src/styles.css`:

```css
.user-message {
  margin-left: 42px;
  background: #dbeafe;
  color: #1e3a8a;
  border-radius: 8px;
  padding: 12px;
}

.agent-messages {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
```

- [ ] **Step 5: Build frontend**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS.

- [ ] **Step 6: Run backend tests**

Run: `pytest tests/server -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src
git commit -m "feat: 接入Agent抽屉对话"
```

---

### Task 11: Update Docs, Run Full Verification, and Keep Legacy Streamlit

**Files:**
- Modify: `docs/frontend-migration.md`
- Test: all backend tests and frontend build.

- [ ] **Step 1: Update migration docs**

Append to `docs/frontend-migration.md`:

```markdown
## MVP 工作台落地路径

新的主前端从 `frontend/` 开始，使用 Vite + React。新的 API 服务从 `server/` 开始，使用 FastAPI + SQLite。当前 `web/` Streamlit 入口保留为 legacy，不在第一阶段删除。

第一阶段只迁移深度投研任务、报告列表/详情、Agent 小球/抽屉和当前页面上下文。Factor Lab、Strategy Lab、Paper Trading、Orders & Positions、Review & Analytics 先作为灰态入口展示。
```

- [ ] **Step 2: Run backend unit tests**

Run:

```bash
pytest tests/server tests/test_signal_processing.py tests/test_ticker_symbol_handling.py -v
```

Expected: PASS.

- [ ] **Step 3: Run frontend build**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS.

- [ ] **Step 4: Smoke run FastAPI app**

Run:

```bash
uvicorn server.main:app --host 127.0.0.1 --port 8000
```

Expected: server starts and logs `Uvicorn running on http://127.0.0.1:8000`. Stop with `Ctrl+C` after checking.

- [ ] **Step 5: Smoke run frontend app**

Run:

```bash
cd frontend
npm run dev
```

Expected: Vite starts on `http://127.0.0.1:5173`. Open the page and verify the sidebar, Deep Research, Reports, Settings, and Agent orb render. Stop with `Ctrl+C` after checking.

- [ ] **Step 6: Check git status**

Run:

```bash
git status --short
```

Expected: only intentional changes are listed before commit.

- [ ] **Step 7: Commit**

```bash
git add docs/frontend-migration.md
git commit -m "docs: 更新前端迁移路径"
```

---

## Self-Review

Spec coverage:

- Vite + React workbench: Tasks 8-10.
- FastAPI service: Tasks 1 and 5.
- SQLite: Task 2.
- SSE research progress: Tasks 4 and 5.
- Default user/workspace with future identity fields: Task 2.
- Current page context only: Tasks 5 and 10.
- Agent small ball + right drawer: Tasks 8 and 10.
- Report flow Tabs and final decision raw view: Task 9.
- DeepResearchTool and ReportSummaryTool: Tasks 6 and 7.
- `web/` retained as legacy: Task 11 docs and no deletion tasks.
- Future factor/backtest/trading modules kept out of Phase 1: frontend gray nav in Task 8 and no backend implementation tasks.

Placeholder scan:

- The plan intentionally uses “future” only for non-implemented extension points from the approved spec.
- No implementation step asks the implementer to invent unspecified behavior.
- No task depends on Streamlit session state.

Type consistency:

- `error_message` and `failed_stage` match the approved spec.
- Frontend `trade_date` maps API snake_case while UI state uses `tradeDate`.
- `report_id`, `task_id`, `session_id`, `user_id`, and `workspace_id` remain string IDs throughout.
