# Architecture & Documentation

# Documentation

## Architecture Diagram

See the Mermaid diagram in the root [README.md](../README.md#architecture).

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Time-series DB | InfluxDB 2.x (Flux) | Modern API, built-in UI, token auth |
| Industrial protocol | OPC-UA via asyncua | More control than Node-RED OPC-UA node, demonstrates Python depth |
| Dashboards | Grafana file provisioning | Reproducible, no manual setup, version-controlled |
| API framework | FastAPI | Async, auto-gen OpenAPI docs, native Pydantic integration |
| ERP data source | Bundled CSV | Self-contained, no external dependencies |
| Alerting | Grafana → FastAPI webhook | Works offline, no external services required |

## Data Models

### InfluxDB Measurements

| Measurement | Tags | Fields | Source |
|-------------|------|--------|--------|
| `sensor_readings` | machine_id, metric | value | Node-RED (from MQTT) |
| `opcua_status` | machine_id | status (0=Running, 1=Idle, 2=Fault) | OPC-UA server |
| `opcua_energy` | machine_id | energy_kwh | OPC-UA server |
| `anomalies` | machine_id, metric | value, z_score, mean, std | Anomaly detector |

### PostgreSQL Tables

| Table | Key Columns | Source |
|-------|-------------|--------|
| `machines` | machine_id, name, type, location | Seed data (init.sql) |
| `alerts` | machine_id, metric, value, threshold, severity, status | Grafana webhook → FastAPI |
| `erp_data` | machine_id, production_date, units_produced, energy_kwh | ERP ingestion |
| `data_quality_log` | source, issue_type, field_name, details | Quality checker |
