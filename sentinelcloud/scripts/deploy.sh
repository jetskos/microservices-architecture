#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
K8S_DIR="$ROOT_DIR/k8s"

IMAGES=(
  "sentinelcloud/auth-service:latest|$ROOT_DIR/auth-service"
  "sentinelcloud/reservation-service:latest|$ROOT_DIR/reservation-service"
  "sentinelcloud/resource-service:latest|$ROOT_DIR/resource-service"
)

echo "[INFO] Build des images..."
for item in "${IMAGES[@]}"; do
  image="${item%%|*}"
  context="${item##*|}"
  echo "[INFO] docker build $image"
  docker build -t "$image" "$context"
done

if ! command -v trivy >/dev/null 2>&1; then
  echo "[ERROR] trivy est requis pour la phase Shift-Left security." >&2
  exit 1
fi

echo "[INFO] Scan vulnérabilités (bloquant sur CRITICAL)..."
for item in "${IMAGES[@]}"; do
  image="${item%%|*}"
  echo "[INFO] trivy image --severity CRITICAL --exit-code 1 $image"
  trivy image --quiet --severity CRITICAL --ignore-unfixed --exit-code 1 "$image"
done

echo "[INFO] Application des manifestes Kubernetes..."
kubectl apply -f "$K8S_DIR/namespace.yaml"
kubectl apply -f "$K8S_DIR/auth-deployment.yaml"
kubectl apply -f "$K8S_DIR/reservation-deployment.yaml"
kubectl apply -f "$K8S_DIR/resource-deployment.yaml"
kubectl apply -f "$K8S_DIR/keycloak-deployment.yaml"
kubectl apply -f "$K8S_DIR/loki-deployment.yaml"
kubectl apply -f "$K8S_DIR/promtail-daemonset.yaml"
kubectl apply -f "$K8S_DIR/prometheus-deployment.yaml"
kubectl apply -f "$K8S_DIR/grafana-deployment.yaml"
kubectl apply -f "$K8S_DIR/network-policy.yaml"
kubectl apply -f "$K8S_DIR/ingress.yaml"

echo "[OK] Déploiement SentinelCloud terminé."
