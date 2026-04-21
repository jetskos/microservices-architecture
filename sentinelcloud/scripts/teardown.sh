#!/usr/bin/env bash
set -euo pipefail

echo "[INFO] Suppression du namespace sentinelcloud..."
kubectl delete namespace sentinelcloud --ignore-not-found=true

echo "[OK] Teardown terminé."
