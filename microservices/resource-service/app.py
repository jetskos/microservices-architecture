from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, cast

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

REGISTRY = CollectorRegistry()
REQUESTS = Counter(
    "resource_requests_total", "Total requests", ["path", "method", "status"], registry=REGISTRY
)
LATENCY = Histogram(
    "resource_request_latency_seconds", "Request latency", ["path", "method"], registry=REGISTRY
)
ERRORS = Counter("resource_errors_total", "Total errors", ["path"], registry=REGISTRY)
ACCESS_DENIED = Counter("resource_access_denied_total", "Access denied events", registry=REGISTRY)

app = FastAPI(title="resource-service")

PATIENT_RECORDS: dict[str, dict[str, str]] = {
    "patient1": {"name": "Alice Patient", "medical_record": "Routine checkup"},
    "patient2": {"name": "Bob Patient", "medical_record": "Dental cleaning"},
}


class UpdateRecord(BaseModel):
    medical_record: str


def audit_log(event: str, **payload: Any) -> None:
    print(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "service": "resource-service",
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


def can_read_record(user: dict[str, Any], patient_id: str) -> bool:
    role = user.get("role")
    if role in {"dentist", "admin", "service"}:
        return True
    return role == "patient" and user.get("sub") == patient_id


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(
        generate_latest(REGISTRY).decode("utf-8"), media_type=CONTENT_TYPE_LATEST
    )


@app.get("/records/{patient_id}")
async def get_record(
    patient_id: str, user: dict[str, Any] = Depends(get_current_user)
) -> dict[str, Any]:
    if not can_read_record(user, patient_id):
        ACCESS_DENIED.inc()
        audit_log("rbac_denied", user=user.get("sub"), role=user.get("role"), patient_id=patient_id)
        raise HTTPException(status_code=403, detail="Forbidden")

    record = PATIENT_RECORDS.get(patient_id)
    if not record:
        raise HTTPException(status_code=404, detail="Patient not found")

    audit_log("record_read", user=user.get("sub"), role=user.get("role"), patient_id=patient_id)
    return {"patient_id": patient_id, **record}


@app.put("/records/{patient_id}")
async def update_record(
    patient_id: str,
    payload: UpdateRecord,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    if user.get("role") != "admin":
        ACCESS_DENIED.inc()
        audit_log(
            "rbac_denied", user=user.get("sub"), role=user.get("role"), action="update_record"
        )
        raise HTTPException(status_code=403, detail="Admin role required")

    if patient_id not in PATIENT_RECORDS:
        raise HTTPException(status_code=404, detail="Patient not found")

    PATIENT_RECORDS[patient_id]["medical_record"] = payload.medical_record
    audit_log("record_updated", user=user.get("sub"), patient_id=patient_id)
    return {"updated": True}
