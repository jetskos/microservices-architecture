import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

RESOURCE_APP_PATH = Path(__file__).resolve().parents[2] / "microservices" / "resource-service" / "app.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_unauthorized_access_without_token() -> None:
    resource_module = load_module(RESOURCE_APP_PATH, "resource_security_unauth")
    client = TestClient(resource_module.app)

    resp = client.get("/records/patient1")
    assert resp.status_code == 401
