# Microservices Architecture with Cybersecurity Focus

## Quick start
```bash
docker-compose up --build
```

Services:
- Auth: `http://localhost:8001`
- Resource: `http://localhost:8002`
- Reservation: `http://localhost:8003`
- Gateway: `http://localhost:8080`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`
- Kibana: `http://localhost:5601`

## Security features
- JWT auth + expiration
- RBAC (`patient`, `dentist`, `admin`)
- Service-to-service Bearer token from Auth-Service
- Structured JSON audit logging

## Local quality checks
```bash
python -m pip install -r requirements-dev.txt
pytest
flake8 .
mypy microservices/auth-service
mypy microservices/resource-service
mypy microservices/reservation-service
```
