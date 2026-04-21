import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

AUTH_APP_PATH = Path(__file__).resolve().parents[2] / "microservices" / "auth-service" / "app.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_invalid_token_is_rejected() -> None:
    auth_module = load_module(AUTH_APP_PATH, "auth_security_token")
    client = TestClient(auth_module.app)

    resp = client.post("/validate", json={"token": "invalid"})
    assert resp.status_code == 200
    assert resp.json()["active"] is False
