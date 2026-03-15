## Plan: Industrial IoT Data Pipeline Portfolio

Build a fully containerized Industrial IoT data pipeline that simulates factory sensor data, ingests it via MQTT and OPC-UA, validates and stores it in InfluxDB + PostgreSQL, visualizes it in Grafana with alerting, and exposes processed data via FastAPI. Everything runs with one `docker compose up`.

---

### Phase 1 — Infrastructure & Data Sources (Week 1)

**Step 1: Project scaffolding**
- Create root `industrial-iot-pipeline/` with this structure:
  ```
  industrial-iot-pipeline/
  ├── docker-compose.yml
  ├── simulator/            # Python sensor simulator
  ├── ingestion/            # Python ERP ingest + Pydantic models
  ├── api/                  # FastAPI backend
  ├── anomaly/              # Z-score anomaly detector
  ├── opcua_server/         # OPC-UA server simulator
  ├── grafana/provisioning/ # Datasources, dashboards, alerting YAML/JSON
  ├── nodered/              # Exported Node-RED flows
  ├── db/                   # PostgreSQL init SQL
  ├── docs/                 # Architecture diagram, assets
  └── .env.example
  ```

**Step 2: Docker Compose base services**
- `mosquitto` (eclipse-mosquitto:2) — ports 1883/9001, config for anonymous local access
- `influxdb` (influxdb:2) — init org/bucket/token via env vars
- `grafana` (grafana/grafana-oss) — mount provisioning dir for auto-configured datasources
- `postgres` (postgres:16) — mount `db/init.sql` for schema on first boot
- `minio` (minio/minio) — console on 9001, init default bucket
- `nodered` (nodered/node-red) — mount flows, install MQTT + InfluxDB palette nodes
- All services on a shared Docker network; health checks + `depends_on` with `condition: service_healthy`

**Step 3: Python sensor simulator** (`simulator/simulator.py`)
- Publishes JSON to MQTT topics every 1–2s using `paho-mqtt`
- Topics: `factory/machine-{id}/temperature`, `.../rpm`, `.../pressure`
- 3–5 simulated machines with realistic distributions (temp ~70–90°C, RPM ~1200–1800, pressure ~2.0–4.5 bar)
- ~5% anomalous readings injected for demo
- Message schema: `{ "machine_id", "metric", "value", "unit", "timestamp" }`

**Step 4: Node-RED MQTT → InfluxDB flow**
- Subscribe to `factory/#` wildcard
- Parse JSON, write to InfluxDB measurement `sensor_readings` with tags `machine_id`, `metric`
- Export flow JSON to `nodered/flows.json` for version control

---

### Phase 2 — Multi-Source Integration (Week 2)

**Step 5: OPC-UA server + client** (*parallel with Step 6*)
- `opcua_server/server.py`: OPC-UA server via `asyncua` exposing machine status (running/idle/fault) and energy consumption on port 4840
- OPC-UA client script polls values and writes to InfluxDB
- Demonstrates the specific industrial protocol

**Step 6: REST/CSV ingestion** (*parallel with Step 5*)
- `ingestion/erp_ingest.py`: Reads a bundled factory energy CSV, parses with Pandas, validates with Pydantic, writes normalized records to PostgreSQL, archives raw files to MinIO
- Runs on a schedule (APScheduler or simple loop)

**Step 7: Pydantic validation & data quality**
- `ingestion/models.py`: `SensorReading` model (with range validators per metric) + `ERPRecord` model
- `ingestion/quality.py`: Missing value detection, out-of-range flagging, duplicate detection
- Quality metrics written to PostgreSQL `data_quality_log` table

**Step 8: PostgreSQL schema** (`db/init.sql`)
- `machines` — device registry (id, name, type, location, commissioned_date)
- `alerts` — alert log (machine_id, metric, value, threshold, severity, timestamps)
- `erp_data` — ingested ERP records
- `data_quality_log` — quality issue tracking

---

### Phase 3 — Dashboard & Alerting (Week 3)

**Step 9: Grafana datasource provisioning**
- `grafana/provisioning/datasources/datasources.yml` — InfluxDB (Flux) + PostgreSQL, auto-loaded on startup

**Step 10: Grafana dashboards** (*parallel with Step 11*)
- All provisioned via JSON files in `grafana/provisioning/dashboards/`
- **Live Sensor Readings**: Real-time gauges + time series for all machines
- **Historical Trends**: Selectable time ranges, machine comparison panels
- **Machine Overview**: Table from PostgreSQL `machines` + latest readings + data quality summary
- **Alerts History**: Table from PostgreSQL `alerts`

**Step 11: Threshold-based alerting** (*parallel with Step 10*)
- Grafana alert rules: temp > 85°C (warning), temp > 95°C (critical), RPM outside 1000–2000, pressure > 4.0 bar
- Contact point: Webhook → FastAPI endpoint that logs to PostgreSQL `alerts` table
- Slack webhook documented as optional add-on

**Step 12: Anomaly detection script** (`anomaly/detector.py`)
- Queries last N minutes from InfluxDB, computes rolling mean + Z-score per machine/metric
- Flags |Z| > 3 as anomalies, writes results back to InfluxDB `anomalies` measurement
- Runs every 60s in its own container

---

### Phase 4 — API & Polish (Week 4)

**Step 13: FastAPI backend** (`api/main.py`)
- `GET /machines` — list all machines
- `GET /machines/{id}/readings?last=1h` — recent readings from InfluxDB
- `GET /machines/{id}/alerts` — alert history
- `GET /health` — health check for all downstream services
- `POST /alerts/acknowledge/{id}` — acknowledge an alert
- `POST /webhooks/grafana-alert` — receive Grafana alert webhooks → write to PostgreSQL

**Step 14: Documentation & README**
- Architecture diagram (Mermaid in README or draw.io PNG)
- Tech stack table, prerequisites, quick start (`docker compose up -d`)
- Screenshots of Grafana dashboards, link to FastAPI Swagger at `/docs`

**Step 15: One-command deployment hardening**
- `.env.example` with all configurable values
- Health checks on all services with proper `depends_on` ordering
- Named volumes for data persistence
- `docker-compose.override.yml` for dev hot-reload

**Step 16: Demo video**
- Screen-record the full flow: compose up → sensors flowing → Node-RED → Grafana dashboards → alert trigger → FastAPI Swagger
- Under 3 minutes, host on YouTube or GIF in README

---

### Relevant Files

| File | Purpose |
|---|---|
| `docker-compose.yml` | All 8+ services, networking, volumes, health checks |
| `simulator/simulator.py` | MQTT sensor publisher with realistic distributions |
| `ingestion/erp_ingest.py` | CSV/REST ingestion with Pandas |
| `ingestion/models.py` | Pydantic validation models |
| `ingestion/quality.py` | Data quality checks |
| `nodered/flows.json` | Node-RED flow (MQTT → InfluxDB) |
| `db/init.sql` | PostgreSQL schema |
| `grafana/provisioning/datasources/datasources.yml` | Auto-configured datasources |
| `grafana/provisioning/dashboards/*.json` | Pre-built dashboards |
| `opcua_server/server.py` | OPC-UA server simulator |
| `anomaly/detector.py` | Z-score anomaly detection |
| `api/main.py` | FastAPI endpoints |
| `README.md` | Full docs + architecture diagram |

---

### Verification

1. `docker compose up -d` starts all services; `docker compose ps` shows all healthy
2. `mosquitto_sub -t "factory/#"` shows JSON sensor messages every 1–2s
3. InfluxDB UI (localhost:8086) → Data Explorer → `sensor_readings` shows data for all machines
4. Node-RED (localhost:1880) shows active flow with message counts
5. PostgreSQL: `SELECT count(*) FROM machines` returns seeded devices; `erp_data` has ingested rows
6. MinIO Console (localhost:9001) shows archived raw files
7. Grafana (localhost:3000) loads all 4 dashboards with live data
8. Trigger temperature spike → Grafana alert fires → appears in PostgreSQL `alerts` table
9. FastAPI Swagger (localhost:8000/docs) → all endpoints return valid responses
10. Anomaly detector logs show periodic runs detecting spikes
11. Full restart: `docker compose down -v && docker compose up -d` — everything recovers

---

### Decisions

- **InfluxDB 2.x** (Flux queries) over 1.x — modern API, built-in UI, token auth
- **OPC-UA via `asyncua`** rather than Node-RED OPC-UA node — more control, demonstrates Python depth
- **Grafana provisioning via files** — ensures reproducibility, no manual setup
- **FastAPI** over Flask — async, auto-gen OpenAPI docs, native Pydantic integration
- **Bundled CSV** for mock ERP data — self-contained, no external dependencies
- **Excluded**: Real cloud deployment — out of scope, but architecture is cloud-ready

---

### Further Considerations

1. **OPC-UA depth**: Should the server simulate a full device object tree with methods, or just flat variables? **Recommendation**: Flat variables with a clean namespace — simpler, still demonstrates the protocol clearly.
2. **Mock ERP source**: Bundled static CSV (simple) vs. a tiny FastAPI mock server serving paginated JSON (more realistic)? **Recommendation**: Bundled CSV as default, document how to swap for a live endpoint.
3. **Grafana alerting contact point**: Webhook to FastAPI only (works offline) vs. also Slack? **Recommendation**: Webhook as default, Slack documented as optional in README.
