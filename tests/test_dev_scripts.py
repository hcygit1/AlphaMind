from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_dev_server_script_starts_backend_with_safe_no_proxy():
    script = PROJECT_ROOT / "scripts" / "dev_server.sh"

    assert script.exists()
    assert script.stat().st_mode & 0o111

    content = script.read_text()
    assert "NO_PROXY=127.0.0.1,localhost,127.0.0.0/8" in content
    assert "no_proxy=127.0.0.1,localhost,127.0.0.0/8" in content
    assert "ALPHAMIND_CORS_ORIGINS=" in content
    assert "http://127.0.0.1:5173" in content
    assert "http://localhost:5173" in content
    assert "uvicorn" in content
    assert "server.main:app" in content


def test_dev_frontend_script_starts_vite_frontend():
    script = PROJECT_ROOT / "scripts" / "dev_frontend.sh"

    assert script.exists()
    assert script.stat().st_mode & 0o111

    content = script.read_text()
    assert "frontend" in content
    assert "npm run dev" in content
