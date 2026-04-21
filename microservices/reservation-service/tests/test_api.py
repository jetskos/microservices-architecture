import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

MODULE_PATH = Path(__file__).resolve().parents[1] / "app.py"
spec = importlib.util.spec_from_file_location("reservation_service_app_api", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

client = TestClient(module.app)


def test_health() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200


def test_missing_token_on_list() -> None:
    resp = client.get("/appointments")
    assert resp.status_code == 401
