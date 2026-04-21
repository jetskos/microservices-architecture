import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

MODULE_PATH = Path(__file__).resolve().parents[1] / "app.py"
spec = importlib.util.spec_from_file_location("resource_service_app", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

client = TestClient(module.app)


def make_token(user: str, role: str) -> str:
    return module.jwt.encode({"sub": user, "role": role}, module.JWT_SECRET, algorithm=module.JWT_ALGORITHM)


def test_patient_cannot_read_other_patient() -> None:
    token = make_token("patient1", "patient")
    resp = client.get("/records/patient2", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_dentist_can_read_patient_record() -> None:
    token = make_token("dentist1", "dentist")
    resp = client.get("/records/patient1", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
