import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

AUTH_APP_PATH = Path(__file__).resolve().parents[2] / "microservices" / "auth-service" / "app.py"
RESOURCE_APP_PATH = Path(__file__).resolve().parents[2] / "microservices" / "resource-service" / "app.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_login_and_access_protected_resource() -> None:
    auth_module = load_module(AUTH_APP_PATH, "auth_integration")
    resource_module = load_module(RESOURCE_APP_PATH, "resource_integration")

    auth_client = TestClient(auth_module.app)
    resource_client = TestClient(resource_module.app)

    login = auth_client.post("/login", json={"username": "dentist1", "password": "dentist-pass"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    resource = resource_client.get("/records/patient1", headers={"Authorization": f"Bearer {token}"})
    assert resource.status_code == 200
