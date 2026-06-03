from fastapi.testclient import TestClient

from server.main import create_app


def test_create_app_exposes_healthcheck():
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
