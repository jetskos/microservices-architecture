#!/usr/bin/env bash
set -euo pipefail

KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8080}"
REALM="${REALM:-sentinelcloud}"
CLIENT_ID="${CLIENT_ID:-sentinelcloud-api}"
USERNAME="${USERNAME:-dev-user}"
PASSWORD="${PASSWORD:-dev-password}"

if ! command -v jq >/dev/null 2>&1; then
  echo "[ERROR] jq est requis" >&2
  exit 1
fi

TOKEN_RESPONSE="$(curl -sS -X POST "$KEYCLOAK_URL/realms/$REALM/protocol/openid-connect/token" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode "grant_type=password" \
  --data-urlencode "client_id=$CLIENT_ID" \
  --data-urlencode "username=$USERNAME" \
  --data-urlencode "password=$PASSWORD")"

ACCESS_TOKEN="$(echo "$TOKEN_RESPONSE" | jq -r '.access_token // empty')"

if [[ -z "$ACCESS_TOKEN" ]]; then
  echo "[ERROR] Impossible de générer le token. Réponse Keycloak:" >&2
  echo "$TOKEN_RESPONSE" >&2
  exit 1
fi

echo "$ACCESS_TOKEN"
