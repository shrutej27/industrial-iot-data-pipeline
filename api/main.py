"""FastAPI backend — exposes machines, readings, alerts, health, and Grafana webhook."""

import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import psycopg2
import psycopg2.extras
import psycopg2.pool
from fastapi import FastAPI, HTTPException, Request
from influxdb_client import InfluxDBClient
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("api")

# ── Configuration ────────────────────────────────────────────────────────────
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
INFLUXDB_TOKEN = os.environ["INFLUXDB_TOKEN"]
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "factory")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "iot")

POSTGRES_DSN = (
    f"host={os.getenv('POSTGRES_HOST', 'postgres')} "
    f"port={os.getenv('POSTGRES_PORT', '5432')} "
    f"dbname={os.getenv('POSTGRES_DB', 'iot_pipeline')} "
    f"user={os.getenv('POSTGRES_USER', 'iot')} "
    f"password={os.environ['POSTGRES_PASSWORD']}"
)

# ── Shared clients ───────────────────────────────────────────────────────────
influx_client: Optional[InfluxDBClient] = None
pg_pool: Optional[psycopg2.pool.SimpleConnectionPool] = None

_DURATION_RE = re.compile(r"^\d+[smhd]$")
_MACHINE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global influx_client, pg_pool
    influx_client = InfluxDBClient(
        url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG
    )
    pg_pool = psycopg2.pool.SimpleConnectionPool(1, 10, POSTGRES_DSN)
    logger.info("FastAPI started")
    yield
    influx_client.close()
    pg_pool.closeall()


app = FastAPI(title="Industrial IoT API", version="1.0.0", lifespan=lifespan)


def _pg():
    return pg_pool.getconn()


def _pg_put(conn):
    pg_pool.putconn(conn)


# ── Pydantic response models ────────────────────────────────────────────────
class Machine(BaseModel):
    id: int
    machine_id: str
    name: str
    type: str
    location: str
    commissioned_date: str


class Alert(BaseModel):
    id: int
    machine_id: str
    metric: str
    value: float
    threshold: float
    severity: str
    status: str
    fired_at: str
    acknowledged_at: Optional[str] = None


class GrafanaAlertEntry(BaseModel):
    """Single alert in unified alerting payload."""

    model_config = {"extra": "allow"}

    status: str = ""
    labels: dict = {}
    annotations: dict = {}
    values: dict = {}


class GrafanaAlert(BaseModel):
    """Grafana Unified Alerting webhook payload."""

    model_config = {"extra": "allow"}

    status: str = ""
    alerts: list[GrafanaAlertEntry] = []
    # Legacy fields (ignored, kept for compatibility)
    title: str = ""
    state: str = ""
    ruleName: str = ""
    message: str = ""
    evalMatches: list = []


class HealthStatus(BaseModel):
    status: str
    influxdb: str
    postgres: str


# ── Endpoints ────────────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthStatus)
async def health():
    influx_ok = "ok"
    pg_ok = "ok"

    try:
        influx_client.ping()
    except Exception:
        influx_ok = "error"

    try:
        conn = _pg()
        _pg_put(conn)
    except Exception:
        pg_ok = "error"

    overall = "ok" if influx_ok == "ok" and pg_ok == "ok" else "degraded"
    return HealthStatus(status=overall, influxdb=influx_ok, postgres=pg_ok)


@app.get("/machines", response_model=list[Machine])
async def list_machines():
    conn = _pg()
    with conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, machine_id, name, type, location, commissioned_date::text FROM machines ORDER BY id"
            )
            rows = cur.fetchall()
    _pg_put(conn)
    return [Machine(**r) for r in rows]


@app.get("/machines/{machine_id}/readings")
async def get_readings(machine_id: str, last: str = "1h"):
    # Validate inputs BEFORE query construction to prevent Flux injection
    if not _MACHINE_ID_RE.match(machine_id):
        raise HTTPException(status_code=400, detail="Invalid machine_id")
    if not _DURATION_RE.match(last):
        raise HTTPException(
            status_code=400, detail="Invalid duration — use e.g. 1h, 30m, 5s, 2d"
        )

    query = f"""
    from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: -{last})
        |> filter(fn: (r) => r._measurement == "sensor_readings")
        |> filter(fn: (r) => r.machine_id == "{machine_id}")
        |> filter(fn: (r) => r._field == "value")
        |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
        |> sort(columns: ["_time"], desc: true)
        |> limit(n: 100)
    """

    tables = influx_client.query_api().query(query)
    results = []
    for table in tables:
        for record in table.records:
            results.append(
                {
                    "time": record.get_time().isoformat(),
                    "machine_id": record.values.get("machine_id"),
                    "metric": record.values.get("metric"),
                    "value": record.values.get("value"),
                }
            )
    return results


@app.get("/machines/{machine_id}/alerts", response_model=list[Alert])
async def get_alerts(machine_id: str):
    conn = _pg()
    with conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT id, machine_id, metric, value, threshold, severity, status,
                          fired_at::text, acknowledged_at::text
                   FROM alerts WHERE machine_id = %s ORDER BY fired_at DESC LIMIT 50""",
                (machine_id,),
            )
            rows = cur.fetchall()
    _pg_put(conn)
    return [Alert(**r) for r in rows]


@app.post("/alerts/acknowledge/{alert_id}")
async def acknowledge_alert(alert_id: int):
    conn = _pg()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE alerts SET status = 'acknowledged', acknowledged_at = %s WHERE id = %s AND status = 'active'",
                (datetime.now(timezone.utc), alert_id),
            )
            if cur.rowcount == 0:
                _pg_put(conn)
                raise HTTPException(
                    status_code=404, detail="Alert not found or already acknowledged"
                )
    _pg_put(conn)
    return {"status": "acknowledged", "alert_id": alert_id}


@app.post("/webhooks/grafana-alert")
async def grafana_alert_webhook(request: Request):
    """Receives Grafana alert webhook and writes to PostgreSQL alerts table."""
    body = await request.json()
    logger.info(
        "Received Grafana alert: status=%s, alerts=%d",
        body.get("status"),
        len(body.get("alerts", [])),
    )

    inserted = 0
    for alert in body.get("alerts", []):
        if alert.get("status") != "firing":
            continue
        labels = alert.get("labels", {})
        machine_id = labels.get("machine_id", "unknown")
        metric = labels.get("alertname", labels.get("metric", "unknown"))
        # Extract first numeric value from alert values
        value = 0.0
        for v in (alert.get("values") or {}).values():
            try:
                value = float(v)
                break
            except (TypeError, ValueError):
                continue
        severity = "critical" if "critical" in metric.lower() else "warning"

        conn = _pg()
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO alerts (machine_id, metric, value, threshold, severity)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (machine_id, metric, value, value, severity),
                )
        _pg_put(conn)
        inserted += 1

    return {"status": "received", "inserted": inserted}
