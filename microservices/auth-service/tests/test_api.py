import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

MODULE_PATH = Path(__file__).resolve().parents[1] / "app.py"
spec = importlib.util.spec_from_file_location("auth_service_app_api", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

client = TestClient(module.app)


def test_health() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_service_token_invalid_api_key() -> None:
    resp = client.post(
        "/service-token",
        json={"service_name": "reservation-service", "api_key": "bad"},
    )
    assert resp.status_code == 401
