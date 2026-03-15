# FastAPI Backend

REST API exposing machine data, alerts, and health checks.

## Endpoints

- `GET /machines` — list all machines
- `GET /machines/{id}/readings?last=1h` — recent readings from InfluxDB
- `GET /machines/{id}/alerts` — alert history
- `GET /health` — health check for all downstream services
- `POST /alerts/acknowledge/{id}` — acknowledge an alert
- `POST /webhooks/grafana-alert` — receive Grafana alert webhooks
