# Ingestion Service

ERP CSV ingestion with Pydantic validation and data quality checks.

## Components

- `erp_ingest.py` — Reads factory energy CSV, validates, writes to PostgreSQL, archives to MinIO
- `models.py` — Pydantic v2 models (SensorReading, ERPRecord)
- `quality.py` — Missing value detection, out-of-range flagging, duplicate detection
