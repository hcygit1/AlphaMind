from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.db.repositories import upsert_report
from server.main import create_app


class FakeResearchService:
    def __init__(self, fail_create: bool = False):
        self.fail_create = fail_create
        self.events: dict[str, list[dict]] = {}
        self.tasks: dict[str, dict] = {}
        self.started_tasks: list[str] = []
        self.task_status = "completed"

    def create_task(self, ticker: str, trade_date: str):
        if self.fail_create:
            raise RuntimeError("同一默认用户同时只能运行一个深度投研任务")
        task = {
            "id": "task_1",
            "ticker": ticker,
            "trade_date": trade_date,
            "status": "pending",
            "progress_stage": None,
        }
        self.tasks[task["id"]] = task
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
        self.started_tasks.append(task_id)
        return None

    def get_task(self, task_id: str):
        task = self.tasks.get(task_id)
        if not task:
            return {}
        return {**task, "status": self.task_status}

    def get_events(self, task_id: str):
        return self.events.get(task_id, [])


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setenv("ALPHAMIND_DB_PATH", str(db_path))
    service = FakeResearchService()
    app = create_app(research_service=service)
    return TestClient(app, raise_server_exceptions=False), service


def test_research_report_agent_and_context_routes(client):
    test_client, service = client

    task_response = test_client.post(
        "/api/research/tasks",
        json={"ticker": "300750", "trade_date": "2026-06-03"},
    )
    assert task_response.status_code == 200
    task = task_response.json()
    assert task["ticker"] == "300750"
    assert task["status"] in {"pending", "running"}
    assert service.started_tasks == [task["id"]]

    session_response = test_client.post("/api/agent/sessions", json={"title": "测试会话"})
    assert session_response.status_code == 200
    session = session_response.json()

    message_response = test_client.post(
        f"/api/agent/sessions/{session['id']}/messages",
        json={"content": "请分析当前页面"},
    )
    assert message_response.status_code == 200
    assistant = message_response.json()
    assert assistant["role"] == "assistant"
    assert assistant["tool_cards"] == []

    messages_response = test_client.get(f"/api/agent/sessions/{session['id']}")
    assert messages_response.status_code == 200
    messages = messages_response.json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]

    context_response = test_client.put(
        "/api/runtime/page-context",
        json={
            "session_id": session["id"],
            "page": "deep_research",
            "context": {"ticker": "300750", "trade_date": "2026-06-03"},
        },
    )
    assert context_response.status_code == 200
    assert context_response.json()["page"] == "deep_research"

    read_context_response = test_client.get(
        "/api/runtime/page-context",
        params={"session_id": session["id"]},
    )
    assert read_context_response.status_code == 200
    assert read_context_response.json()["context_json"]["ticker"] == "300750"

    reports_response = test_client.get("/api/reports")
    assert reports_response.status_code == 200
    assert isinstance(reports_response.json(), list)


def test_research_active_task_conflict_returns_409(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ALPHAMIND_DB_PATH", str(tmp_path / "test.sqlite3"))
    app = create_app(research_service=FakeResearchService(fail_create=True))
    test_client = TestClient(app)

    response = test_client.post(
        "/api/research/tasks",
        json={"ticker": "300750", "trade_date": "2026-06-03"},
    )

    assert response.status_code == 409
    assert "同时只能运行一个" in response.json()["detail"]


def test_research_events_stream_uses_injected_shared_service(client):
    test_client, service = client
    task_response = test_client.post(
        "/api/research/tasks",
        json={"ticker": "300750", "trade_date": "2026-06-03"},
    )
    task_id = task_response.json()["id"]
    service.events[task_id].append(
        {
            "event": "research_progress",
            "task_id": task_id,
            "status": "completed",
            "stage": "completed",
            "message": "深度投研完成",
            "payload": {"report_id": "report_1"},
        }
    )

    with test_client.stream("GET", f"/api/research/tasks/{task_id}/events") as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert "event: research_progress" in body
    assert "任务已创建" in body
    assert "深度投研完成" in body


def test_unknown_research_events_task_returns_404(client):
    test_client, _service = client

    response = test_client.get("/api/research/tasks/task_missing/events")

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_invalid_agent_session_send_message_returns_404(client):
    test_client, _service = client

    response = test_client.post(
        "/api/agent/sessions/session_missing/messages",
        json={"content": "请分析当前页面"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Agent session not found"


def test_invalid_agent_session_read_messages_returns_404(client):
    test_client, _service = client

    response = test_client.get("/api/agent/sessions/session_missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Agent session not found"


def test_invalid_page_context_session_returns_404(client):
    test_client, _service = client

    response = test_client.put(
        "/api/runtime/page-context",
        json={
            "session_id": "session_missing",
            "page": "deep_research",
            "context": {"ticker": "300750", "trade_date": "2026-06-03"},
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Agent session not found"


def test_agent_message_returns_report_summary_tool_card(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ALPHAMIND_DB_PATH", str(tmp_path / "test.sqlite3"))
    app = create_app(research_service=FakeResearchService())
    test_client = TestClient(app, raise_server_exceptions=False)
    state_path = tmp_path / "state.json"
    state_path.write_text('{"final_trade_decision":"**Rating**: Hold"}', encoding="utf-8")
    report = upsert_report(
        app.state.database_path,
        "300750",
        "2026-06-03",
        "Hold",
        "宁德时代报告摘要",
        str(state_path),
    )
    session = test_client.post("/api/agent/sessions", json={"title": "报告会话"}).json()
    context_response = test_client.put(
        "/api/runtime/page-context",
        json={
            "session_id": session["id"],
            "page": "report_detail",
            "context": {"active_report_id": report["id"]},
        },
    )
    assert context_response.status_code == 200

    response = test_client.post(
        f"/api/agent/sessions/{session['id']}/messages",
        json={"content": "总结报告"},
    )

    assert response.status_code == 200
    assistant = response.json()
    assert "宁德时代报告摘要" in assistant["content"]
    assert assistant["tool_cards"] == [
        {
            "type": "report_summary",
            "status": "completed",
            "payload": {"report_id": report["id"]},
        }
    ]


def test_agent_message_uses_injected_research_service_for_deep_research(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("ALPHAMIND_DB_PATH", str(tmp_path / "test.sqlite3"))
    service = FakeResearchService()
    app = create_app(research_service=service)
    test_client = TestClient(app, raise_server_exceptions=False)
    session = test_client.post("/api/agent/sessions", json={"title": "投研会话"}).json()
    context_response = test_client.put(
        "/api/runtime/page-context",
        json={
            "session_id": session["id"],
            "page": "deep_research",
            "context": {"ticker": "300750", "trade_date": "2026-06-03"},
        },
    )
    assert context_response.status_code == 200

    response = test_client.post(
        f"/api/agent/sessions/{session['id']}/messages",
        json={"content": "帮我做一次深度投研"},
    )

    assert response.status_code == 200
    assert service.started_tasks == ["task_1"]
    assert response.json()["tool_cards"] == [
        {
            "type": "deep_research",
            "status": "accepted",
            "payload": {
                "task_id": "task_1",
                "ticker": "300750",
                "trade_date": "2026-06-03",
            },
        }
    ]
