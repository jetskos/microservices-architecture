# SentinelCloud

Architecture microservices sécurisée et observable sur Kubernetes, basée sur les principes **Zero-Trust** et **Shift-Left Security**.

## Arborescence

```text
sentinelcloud/
├── auth-service/
├── reservation-service/
├── resource-service/
├── k8s/
├── scripts/
├── .gitignore
└── README.md
```

## Schéma textuel d’architecture

```text
[Client/API Tester]
      |
      v
 [Ingress NGINX]
      |------------------------------|
      v                              v
 [auth-service Django]         [reservation-service FastAPI]
      |                              |
      |                              v
      |                        [resource-service FastAPI]
      |
      v
 [Keycloak OIDC/JWT]

Logs: auth-service + services -> Promtail -> Loki -> Grafana (Logs SOC)
Metrics: services /metrics -> Prometheus -> Grafana (Dashboards + alerting SOC)

NetworkPolicy: default-deny + flux explicitement autorisés
```

## Sécurité implémentée

- **Authentification centralisée OIDC** via Keycloak.
- **RBAC**: mapping rôles Keycloak vers groupes Django (`auth_service/oidc_backend.py`).
- **JWT obligatoire** sur les APIs FastAPI (validation signature RS256 via JWKS Keycloak).
- **Zero-Trust réseau** avec `network-policy.yaml` (default deny + allow-list précise).
- **SOC audit logs** via `SOCAuditMiddleware` avec tags `[SECURITY]` et `[ERROR]`.

## Observabilité implémentée

- Endpoints `/metrics` exposés sur Django/FastAPI via `prometheus_client`.
- Prometheus scrape les 3 services et charge des règles d’alertes SOC:
  - surcharge trafic,
  - erreurs HTTP 5xx,
  - latence p95 élevée.
- Grafana provisionne automatiquement:
  - datasource Prometheus,
  - datasource Loki,
  - dashboard de supervision SentinelCloud.
- Promtail parse les logs et extrait `soc_tag` (`SECURITY`/`ERROR`) pour filtrage rapide dans Loki/Grafana.
- Les stores CRUD FastAPI sont en mémoire (volatils), adaptés à la démo et non à la production.

## Déploiement local (CI/CD simulé)

Depuis le dossier `sentinelcloud/`:

```bash
chmod +x scripts/*.sh
./scripts/deploy.sh
```

Le script:
1. Build les images Docker.
2. Exécute `trivy image` en mode bloquant sur vulnérabilités **CRITICAL**.
3. Applique les manifestes Kubernetes si le scan est conforme.

## Teardown

```bash
./scripts/teardown.sh
```

## Générer un token JWT de dev

```bash
./scripts/gen-dev-token.sh
```

Variables optionnelles:
- `KEYCLOAK_URL`
- `REALM`
- `CLIENT_ID`
- `USERNAME`
- `PASSWORD`

## Tests des scénarios demandés

### A) Sécurité & IdP

1. Générer un token:
```bash
TOKEN=$(./scripts/gen-dev-token.sh)
```
2. Tester une route protégée:
```bash
curl -H "Authorization: Bearer $TOKEN" http://sentinelcloud.local/reservations
```
3. Tester sans token (doit renvoyer 401):
```bash
curl -i http://sentinelcloud.local/reservations
```

### B) Monitoring / anomalies

- Ouvrir Grafana (`kubectl port-forward svc/grafana -n sentinelcloud 3000:3000`).
- Vérifier les panels trafic, erreurs, latence.
- Simuler charge/erreurs puis observer déclenchement des règles Prometheus.

### C) Logs centralisés SOC

- Provoquer un accès interdit / erreur applicative.
- Dans Grafana Explore (Loki), filtrer:
```logql
{namespace="sentinelcloud", soc_tag=~"SECURITY|ERROR"}
```

### D) Shift-Left

- Exécuter `./scripts/deploy.sh`.
- Vérifier qu’un scan Trivy critique stoppe le déploiement (exit code non nul).
