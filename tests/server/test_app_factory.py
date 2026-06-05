from pathlib import Path

from fastapi.testclient import TestClient

from server.db.repositories import upsert_report
from server.main import create_app


class FakeResearchService:
    pass


class FakeAgentService:
    def __init__(self):
        self.created_titles: list[str] = []

    def create_session(self, title: str) -> dict:
        self.created_titles.append(title)
        return {"id": "session_from_app_state", "title": title}


def test_create_app_exposes_healthcheck():
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_app_exposes_shared_agent_service(tmp_path, monkeypatch):
    monkeypatch.setenv("ALPHAMIND_DB_PATH", str(tmp_path / "test.sqlite3"))
    research_service = FakeResearchService()

    app = create_app(research_service=research_service)

    assert app.state.research_service is research_service
    assert app.state.agent_service.research_service is research_service


def test_agent_routes_use_app_state_agent_service(tmp_path, monkeypatch):
    monkeypatch.setenv("ALPHAMIND_DB_PATH", str(tmp_path / "test.sqlite3"))
    app = create_app(research_service=FakeResearchService())
    fake_agent_service = FakeAgentService()
    app.state.agent_service = fake_agent_service
    client = TestClient(app)

    response = client.post("/api/agent/sessions", json={"title": "共享服务会话"})

    assert response.status_code == 200
    assert response.json()["id"] == "session_from_app_state"
    assert fake_agent_service.created_titles == ["共享服务会话"]


def test_report_routes_use_app_state_database_path(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "app.sqlite3"
    other_db_path = tmp_path / "other.sqlite3"
    monkeypatch.setenv("ALPHAMIND_DB_PATH", str(db_path))
    app = create_app(research_service=FakeResearchService())
    state_path = tmp_path / "state.json"
    state_path.write_text('{"final_trade_decision":"**Rating**: Hold"}', encoding="utf-8")
    report = upsert_report(app.state.database_path, "300750", "2026-06-03", "Hold", "摘要", str(state_path))
    monkeypatch.setenv("ALPHAMIND_DB_PATH", str(other_db_path))
    client = TestClient(app)

    list_response = client.get("/api/reports")
    detail_response = client.get(f"/api/reports/{report['id']}")

    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [report["id"]]
    assert detail_response.status_code == 200
    assert detail_response.json()["report"]["id"] == report["id"]
