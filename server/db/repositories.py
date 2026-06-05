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


def create_research_task_if_none_active(
    db_path: Path | str,
    ticker: str,
    trade_date: str,
) -> dict[str, Any]:
    task_id = _uuid("task")
    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        active = conn.execute(
            """
            SELECT id FROM research_tasks
            WHERE user_id = ? AND workspace_id = ? AND status IN ('pending', 'running')
            LIMIT 1
            """,
            (DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID),
        ).fetchone()
        if active:
            raise RuntimeError("同一默认用户同时只能运行一个深度投研任务")
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
            "SELECT * FROM research_reports ORDER BY created_at DESC, trade_date DESC, id DESC"
        ).fetchall()
    return [_dict(row) for row in rows]


def list_active_research_tasks(db_path: Path | str) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM research_tasks
            WHERE user_id = ? AND workspace_id = ? AND status IN ('pending', 'running')
            ORDER BY created_at ASC, id ASC
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


def get_agent_session(db_path: Path | str, session_id: str) -> dict[str, Any]:
    with connect(db_path) as conn:
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
    message = _dict(row)
    message["tool_calls_json"] = json.loads(message["tool_calls_json"])
    return message


def list_agent_messages(db_path: Path | str, session_id: str) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM agent_messages WHERE session_id = ? ORDER BY created_at ASC, rowid ASC",
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
