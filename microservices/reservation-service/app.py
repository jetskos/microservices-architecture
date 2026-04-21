from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, cast

import httpx
import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-prod")
JWT_ALGORITHM = "HS256"
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
RESOURCE_SERVICE_URL = os.getenv("RESOURCE_SERVICE_URL", "http://localhost:8002")
SERVICE_API_KEY = os.getenv("SERVICE_API_KEY", "reservation-secret")

REGISTRY = CollectorRegistry()
REQUESTS = Counter(
    "reservation_requests_total", "Total requests", ["path", "method", "status"], registry=REGISTRY
)
LATENCY = Histogram(
    "reservation_request_latency_seconds", "Request latency", ["path", "method"], registry=REGISTRY
)
ERRORS = Counter("reservation_errors_total", "Total errors", ["path"], registry=REGISTRY)
CREATED_APPOINTMENTS = Counter(
    "appointments_created_total", "Appointments created", registry=REGISTRY
)

app = FastAPI(title="reservation-service")

APPOINTMENTS: list[dict[str, str]] = []


class ReservationRequest(BaseModel):
    patient_id: str
    slot: str


def audit_log(event: str, **payload: Any) -> None:
    print(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "service": "reservation-service",
                "event": event,
                **payload,
            }
        )
    )


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    path = request.url.path
    method = request.method
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    except Exception:
        ERRORS.labels(path=path).inc()
        raise
    finally:
        LATENCY.labels(path=path, method=method).observe(time.perf_counter() - start)
        REQUESTS.labels(path=path, method=method, status=str(status)).inc()


def decode_bearer_token(authorization: str | None) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return cast(dict[str, Any], payload)
    except jwt.PyJWTError as exc:
        audit_log("token_invalid", reason=str(exc))
        raise HTTPException(status_code=401, detail="Invalid token") from exc


def get_current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    return decode_bearer_token(authorization)


async def fetch_service_token() -> str:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(
            f"{AUTH_SERVICE_URL}/service-token",
            json={"service_name": "reservation-service", "api_key": SERVICE_API_KEY},
        )
        response.raise_for_status()
        body = cast(dict[str, str], response.json())
        return body["access_token"]


async def verify_patient_exists(patient_id: str) -> None:
    service_token = await fetch_service_token()
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(
            f"{RESOURCE_SERVICE_URL}/records/{patient_id}",
            headers={"Authorization": f"Bearer {service_token}"},
        )
        if response.status_code >= 400:
            raise HTTPException(status_code=400, detail="Unknown patient")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(
        generate_latest(REGISTRY).decode("utf-8"), media_type=CONTENT_TYPE_LATEST
    )


@app.get("/appointments")
async def list_appointments(
    user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, str]]:
    if user.get("role") in {"dentist", "admin"}:
        return APPOINTMENTS
    return [appt for appt in APPOINTMENTS if appt["patient_id"] == user.get("sub")]


@app.post("/appointments")
async def create_appointment(
    payload: ReservationRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    if user.get("role") == "patient" and user.get("sub") != payload.patient_id:
        audit_log("reservation_denied", user=user.get("sub"), patient_id=payload.patient_id)
        raise HTTPException(
            status_code=403, detail="Patients can only create their own appointments"
        )

    await verify_patient_exists(payload.patient_id)
    APPOINTMENTS.append(
        {"patient_id": payload.patient_id, "slot": payload.slot, "created_by": str(user.get("sub"))}
    )
    CREATED_APPOINTMENTS.inc()
    audit_log("appointment_created", patient_id=payload.patient_id, actor=user.get("sub"))
    return {"created": True}
