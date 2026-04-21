# Architecture

## Services
- Auth-Service: JWT issuing/validation, RBAC identities.
- Resource-Service: protected patient records with RBAC checks.
- Reservation-Service: appointment scheduling and secure service-to-service calls.

## Security Controls
- JWT Bearer authentication across all services.
- Roles: `patient`, `dentist`, `admin`.
- bcrypt password hashing in auth service.
- Security audit logs emitted in JSON.

## Platform
- Nginx API gateway routes `/auth`, `/resource`, `/reservation`.
- Prometheus scrapes `/metrics` on each service.
- Grafana dashboards provisioned from JSON.
- ELK stack receives JSON logs on TCP/5000.
