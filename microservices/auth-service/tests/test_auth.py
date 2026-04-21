import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

MODULE_PATH = Path(__file__).resolve().parents[1] / "app.py"
spec = importlib.util.spec_from_file_location("auth_service_app", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

client = TestClient(module.app)


def test_login_success_and_token_validation() -> None:
    resp = client.post("/login", json={"username": "patient1", "password": "patient-pass"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    validate = client.post("/validate", json={"token": token})
    assert validate.status_code == 200
    assert validate.json()["active"] is True


def test_login_failure() -> None:
    resp = client.post("/login", json={"username": "patient1", "password": "wrong"})
    assert resp.status_code == 401
