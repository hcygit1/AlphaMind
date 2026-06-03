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
