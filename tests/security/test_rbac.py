import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

RESOURCE_APP_PATH = (
    Path(__file__).resolve().parents[2] / "microservices" / "resource-service" / "app.py"
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_rbac_forbids_patient_updating_record() -> None:
    resource_module = load_module(RESOURCE_APP_PATH, "resource_security_rbac")
    client = TestClient(resource_module.app)
    token = resource_module.jwt.encode(
        {"sub": "patient1", "role": "patient"},
        resource_module.JWT_SECRET,
        algorithm=resource_module.JWT_ALGORITHM,
    )

    resp = client.put(
        "/records/patient1",
        json={"medical_record": "hacked"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
