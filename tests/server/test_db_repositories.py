import sqlite3
from pathlib import Path

from server.db.connection import connect
from server.db.connection import init_db
from server.db.repositories import (
    add_agent_message,
    create_agent_session,
    create_research_task,
    get_page_context,
    get_research_task,
    list_agent_messages,
    list_active_research_tasks,
    list_reports,
    save_page_context,
    update_research_task,
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

    running_task = create_research_task(db_path, ticker="600519", trade_date="2026-06-03")
    update_research_task(db_path, running_task["id"], status="running")
    completed_task = create_research_task(db_path, ticker="000001", trade_date="2026-06-03")
    update_research_task(db_path, completed_task["id"], status="completed")
    active_tasks = list_active_research_tasks(db_path)
    assert {active_task["status"] for active_task in active_tasks} == {"pending", "running"}
    assert {active_task["id"] for active_task in active_tasks} == {task["id"], running_task["id"]}

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


def test_agent_messages_require_existing_session(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)

    try:
        add_agent_message(db_path, "missing_session", "user", "hello")
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("expected agent_messages.session_id foreign key to be enforced")


def test_agent_messages_round_trip_json_and_keep_insertion_order(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)
    session = create_agent_session(db_path, title="默认会话")

    user_message = add_agent_message(db_path, session["id"], "user", "请分析")
    assistant_message = add_agent_message(
        db_path,
        session["id"],
        "assistant",
        "分析完成",
        tool_calls=[{"name": "summarize_report", "arguments": {"report_id": "report_1"}}],
    )

    messages = list_agent_messages(db_path, session["id"])
    assert [message["id"] for message in messages] == [user_message["id"], assistant_message["id"]]
    assert messages[0]["tool_calls_json"] == []
    assert messages[1]["tool_calls_json"] == [
        {"name": "summarize_report", "arguments": {"report_id": "report_1"}}
    ]


def test_save_page_context_overwrites_existing_context(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)
    session = create_agent_session(db_path, title="默认会话")

    save_page_context(db_path, session_id=session["id"], page="report_list", context={"filter": "all"})
    save_page_context(
        db_path,
        session_id=session["id"],
        page="report_detail",
        context={"active_report_id": "report_2", "active_tab": "final_decision"},
    )

    page_context = get_page_context(db_path, session["id"])
    assert page_context["page"] == "report_detail"
    assert page_context["context_json"] == {
        "active_report_id": "report_2",
        "active_tab": "final_decision",
    }


def test_update_research_task_ignores_fields_outside_allowlist(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)
    task = create_research_task(db_path, ticker="300750", trade_date="2026-06-03")

    updated = update_research_task(db_path, task["id"], status="running", unexpected="ignored")

    assert updated["status"] == "running"
    assert "unexpected" not in updated


def test_reports_use_stable_tie_breakers_for_same_second_rows(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)
    with connect(db_path) as conn:
        for report_id in ("report_a", "report_z"):
            conn.execute(
                """
                INSERT INTO research_reports
                (id, user_id, workspace_id, ticker, trade_date, signal, summary, state_path, created_at)
                VALUES (?, 'default_user', 'default_workspace', '300750', '2026-06-03', 'Hold', '摘要', '/tmp/state.json', '2026-06-03 10:00:00')
                """,
                (report_id,),
            )

    assert [report["id"] for report in list_reports(db_path)] == ["report_z", "report_a"]


def test_active_research_tasks_use_stable_tie_breakers_for_same_second_rows(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)
    with connect(db_path) as conn:
        for task_id in ("task_z", "task_a"):
            conn.execute(
                """
                INSERT INTO research_tasks
                (id, user_id, workspace_id, ticker, trade_date, status, created_at)
                VALUES (?, 'default_user', 'default_workspace', '300750', '2026-06-03', 'pending', '2026-06-03 10:00:00')
                """,
                (task_id,),
            )

    assert [task["id"] for task in list_active_research_tasks(db_path)] == ["task_a", "task_z"]
