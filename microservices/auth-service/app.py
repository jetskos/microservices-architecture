from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-prod")
JWT_ALGORITHM = "HS256"
SERVICE_API_KEY = os.getenv("SERVICE_API_KEY", "reservation-secret")

REQUESTS = Counter("auth_requests_total", "Total requests", ["path", "method", "status"])
LATENCY = Histogram("auth_request_latency_seconds", "Request latency", ["path", "method"])
ERRORS = Counter("auth_errors_total", "Total errors", ["path"])
AUTH_FAILURES = Counter("auth_failures_total", "Authentication failures")
AUTH_SUCCESSES = Counter("auth_success_total", "Authentication successes")

app = FastAPI(title="auth-service")


def _hashed(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


USERS: dict[str, dict[str, str]] = {
    "patient1": {"password": _hashed("patient-pass"), "role": "patient"},
    "dentist1": {"password": _hashed("dentist-pass"), "role": "dentist"},
    "admin1": {"password": _hashed("admin-pass"), "role": "admin"},
}


class LoginRequest(BaseModel):
    username: str
    password: str


class ServiceTokenRequest(BaseModel):
    service_name: str
    api_key: str


class ValidateRequest(BaseModel):
    token: str


def audit_log(event: str, **payload: Any) -> None:
    print(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "service": "auth-service",
                "event": event,
                **payload,
            }
        )
    )


def create_access_token(subject: str, role: str, expires_minutes: int = 30, token_type: str = "user") -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {"sub": subject, "role": role, "type": token_type, "exp": expires}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)


@app.post("/login")
async def login(data: LoginRequest) -> dict[str, str]:
    user = USERS.get(data.username)
    if not user:
        AUTH_FAILURES.inc()
        audit_log("auth_failure", username=data.username, reason="unknown_user")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not bcrypt.checkpw(data.password.encode("utf-8"), user["password"].encode("utf-8")):
        AUTH_FAILURES.inc()
        audit_log("auth_failure", username=data.username, reason="bad_password")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(data.username, user["role"])
    AUTH_SUCCESSES.inc()
    audit_log("auth_success", username=data.username, role=user["role"])
    return {"access_token": token, "token_type": "bearer"}


@app.post("/validate")
async def validate(data: ValidateRequest) -> dict[str, Any]:
    try:
        payload = decode_token(data.token)
        return {"active": True, "payload": payload}
    except jwt.PyJWTError:
        audit_log("token_validation_failed")
        return {"active": False}


@app.post("/service-token")
async def service_token(data: ServiceTokenRequest) -> dict[str, str]:
    if data.api_key != SERVICE_API_KEY:
        audit_log("service_token_denied", service=data.service_name)
        raise HTTPException(status_code=401, detail="Invalid service credentials")

    token = create_access_token(data.service_name, "service", expires_minutes=5, token_type="service")
    audit_log("service_token_issued", service=data.service_name)
    return {"access_token": token, "token_type": "bearer"}
