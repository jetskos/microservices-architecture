import os
import time
from typing import Dict, Optional
from uuid import uuid4

import requests
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import Response
from jose import jwt
from jose.exceptions import JOSEError
from pydantic import BaseModel, Field
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

app = FastAPI(title="resource-service")

KEYCLOAK_ISSUER = os.getenv("KEYCLOAK_ISSUER", "http://keycloak:8080/realms/sentinelcloud")
KEYCLOAK_JWKS_URL = os.getenv("KEYCLOAK_JWKS_URL", f"{KEYCLOAK_ISSUER}/protocol/openid-connect/certs")
KEYCLOAK_AUDIENCE = os.getenv("KEYCLOAK_AUDIENCE", "sentinelcloud-api")

REQUEST_COUNT = Counter("resource_http_requests_total", "Total requests", ["method", "path", "status"])
REQUEST_LATENCY = Histogram("resource_http_request_latency_seconds", "Request latency", ["method", "path"])

# Store en mémoire (volatile) pour la démo, non adapté à la production.
DB: Dict[str, dict] = {}
JWKS_CACHE: Optional[dict] = None
JWKS_LAST_FETCH = 0.0
JWKS_TTL_SECONDS = 300


class ResourceIn(BaseModel):
    name: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    capacity: int = Field(..., ge=1)


class ResourceOut(ResourceIn):
    id: str


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration = time.monotonic() - start
    path = request.url.path
    REQUEST_COUNT.labels(request.method, path, str(response.status_code)).inc()
    REQUEST_LATENCY.labels(request.method, path).observe(duration)
    return response


def _get_jwks() -> dict:
    global JWKS_CACHE, JWKS_LAST_FETCH
    now = time.time()
    if JWKS_CACHE and now - JWKS_LAST_FETCH < JWKS_TTL_SECONDS:
        return JWKS_CACHE

    response = requests.get(KEYCLOAK_JWKS_URL, timeout=5)
    response.raise_for_status()
    JWKS_CACHE = response.json()
    JWKS_LAST_FETCH = now
    return JWKS_CACHE


def _validate_token(token: str) -> dict:
    try:
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        jwks = _get_jwks().get("keys", [])
        key = next((k for k in jwks if k.get("kid") == kid), None)
        if not key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown signing key")

        return jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=KEYCLOAK_AUDIENCE,
            issuer=KEYCLOAK_ISSUER,
            options={"verify_at_hash": False},
        )
    except (JOSEError, requests.RequestException, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


def require_auth(request: Request) -> dict:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")

    token = auth_header.split(" ", maxsplit=1)[1].strip()
    claims = _validate_token(token)
    return claims


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/resources", response_model=ResourceOut)
def create_resource(payload: ResourceIn, _: dict = Depends(require_auth)) -> ResourceOut:
    item_id = str(uuid4())
    DB[item_id] = {"id": item_id, **payload.model_dump()}
    return ResourceOut(**DB[item_id])


@app.get("/resources", response_model=list[ResourceOut])
def list_resources(_: dict = Depends(require_auth)) -> list[ResourceOut]:
    return [ResourceOut(**item) for item in DB.values()]


@app.get("/resources/{resource_id}", response_model=ResourceOut)
def get_resource(resource_id: str, _: dict = Depends(require_auth)) -> ResourceOut:
    item = DB.get(resource_id)
    if not item:
        raise HTTPException(status_code=404, detail="Resource not found")
    return ResourceOut(**item)


@app.put("/resources/{resource_id}", response_model=ResourceOut)
def update_resource(resource_id: str, payload: ResourceIn, _: dict = Depends(require_auth)) -> ResourceOut:
    if resource_id not in DB:
        raise HTTPException(status_code=404, detail="Resource not found")
    DB[resource_id] = {"id": resource_id, **payload.model_dump()}
    return ResourceOut(**DB[resource_id])


@app.delete("/resources/{resource_id}", status_code=204)
def delete_resource(resource_id: str, _: dict = Depends(require_auth)) -> Response:
    if resource_id not in DB:
        raise HTTPException(status_code=404, detail="Resource not found")
    del DB[resource_id]
    return Response(status_code=204)
