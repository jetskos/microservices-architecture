import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

MODULE_PATH = Path(__file__).resolve().parents[1] / "app.py"
spec = importlib.util.spec_from_file_location("reservation_service_app", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

client = TestClient(module.app)


def make_token(user: str, role: str) -> str:
    return module.jwt.encode({"sub": user, "role": role}, module.JWT_SECRET, algorithm=module.JWT_ALGORITHM)


def test_patient_cannot_create_for_other_patient(monkeypatch) -> None:
    async def _ok(_patient_id: str) -> None:
        return None

    monkeypatch.setattr(module, "verify_patient_exists", _ok)
    token = make_token("patient1", "patient")
    resp = client.post(
        "/appointments",
        json={"patient_id": "patient2", "slot": "2026-05-01T10:00:00Z"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_dentist_can_create_appointment(monkeypatch) -> None:
    async def _ok(_patient_id: str) -> None:
        return None

    monkeypatch.setattr(module, "verify_patient_exists", _ok)
    token = make_token("dentist1", "dentist")
    resp = client.post(
        "/appointments",
        json={"patient_id": "patient1", "slot": "2026-05-01T10:00:00Z"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
