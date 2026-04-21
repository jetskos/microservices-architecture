import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

RES_APP_PATH = (
    Path(__file__).resolve().parents[2] / "microservices" / "reservation-service" / "app.py"
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_reservation_uses_secured_user_token(monkeypatch) -> None:
    reservation_module = load_module(RES_APP_PATH, "reservation_integration")

    async def _ok(_patient_id: str) -> None:
        pass

    monkeypatch.setattr(reservation_module, "verify_patient_exists", _ok)
    client = TestClient(reservation_module.app)
    token = reservation_module.jwt.encode(
        {"sub": "dentist1", "role": "dentist"},
        reservation_module.JWT_SECRET,
        algorithm=reservation_module.JWT_ALGORITHM,
    )

    resp = client.post(
        "/appointments",
        json={"patient_id": "patient1", "slot": "2026-06-01T09:00:00Z"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
