"""ERP CSV ingestion service — reads CSV, validates, writes to PostgreSQL, archives to MinIO."""

import io
import logging
import os
import time

import boto3
import pandas as pd
import psycopg2
from botocore.client import Config

from models import ERPRecord
from quality import QualityChecker

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("erp-ingest")

# ── Configuration ────────────────────────────────────────────────────────────
POSTGRES_DSN = (
    f"host={os.getenv('POSTGRES_HOST', 'postgres')} "
    f"port={os.getenv('POSTGRES_PORT', '5432')} "
    f"dbname={os.getenv('POSTGRES_DB', 'iot_pipeline')} "
    f"user={os.getenv('POSTGRES_USER', 'iot')} "
    f"password={os.environ['POSTGRES_PASSWORD']}"
)

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY = os.environ["MINIO_ROOT_USER"]
MINIO_SECRET_KEY = os.environ["MINIO_ROOT_PASSWORD"]
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "raw-data")

CSV_PATH = os.getenv("CSV_PATH", "/app/data/factory_erp.csv")
INGEST_INTERVAL = int(os.getenv("INGEST_INTERVAL", "300"))  # seconds


class ERPIngestor:
    """Reads CSV, validates rows, writes valid records to PostgreSQL, archives to MinIO."""

    def __init__(self) -> None:
        self._checker = QualityChecker(POSTGRES_DSN)
        self._s3 = boto3.client(
            "s3",
            endpoint_url=MINIO_ENDPOINT,
            aws_access_key_id=MINIO_ACCESS_KEY,
            aws_secret_access_key=MINIO_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        self._ensure_bucket()

    # ── Ensure MinIO bucket exists ───────────────────────────────────────
    def _ensure_bucket(self) -> None:
        try:
            self._s3.head_bucket(Bucket=MINIO_BUCKET)
        except Exception:
            try:
                self._s3.create_bucket(Bucket=MINIO_BUCKET)
                logger.info("Created MinIO bucket '%s'", MINIO_BUCKET)
            except Exception:
                logger.exception("Could not create MinIO bucket '%s'", MINIO_BUCKET)

    # ── Main ingest cycle ────────────────────────────────────────────────
    def run_once(self) -> None:
        logger.info("Starting ERP CSV ingestion from %s", CSV_PATH)

        df = pd.read_csv(CSV_PATH)
        logger.info("Read %d rows from CSV", len(df))

        valid_records, issues = self._checker.check(df)
        logger.info("Validation: %d valid, %d issues", len(valid_records), len(issues))

        if valid_records:
            self._write_to_postgres(valid_records)

        self._archive_to_minio(df)

    # ── Write valid records to PostgreSQL ────────────────────────────────
    def _write_to_postgres(self, records: list[ERPRecord]) -> None:
        try:
            conn = psycopg2.connect(POSTGRES_DSN)
            with conn:
                with conn.cursor() as cur:
                    for rec in records:
                        cur.execute(
                            """INSERT INTO erp_data
                               (machine_id, production_date, units_produced,
                                energy_kwh, defect_count, operator, shift)
                               VALUES (%s, %s, %s, %s, %s, %s, %s)
                               ON CONFLICT DO NOTHING""",
                            (
                                rec.machine_id,
                                rec.production_date,
                                rec.units_produced,
                                rec.energy_kwh,
                                rec.defect_count,
                                rec.operator,
                                rec.shift,
                            ),
                        )
            conn.close()
            logger.info("Inserted %d records into erp_data", len(records))
        except Exception:
            logger.exception("Failed to write ERP records to PostgreSQL")

    # ── Archive raw CSV to MinIO ─────────────────────────────────────────
    def _archive_to_minio(self, df: pd.DataFrame) -> None:
        try:
            ts = time.strftime("%Y%m%dT%H%M%S")
            key = f"erp/factory_erp_{ts}.csv"
            buf = io.BytesIO(df.to_csv(index=False).encode())
            self._s3.upload_fileobj(buf, MINIO_BUCKET, key)
            logger.info("Archived CSV to MinIO as %s", key)
        except Exception:
            logger.exception("Failed to archive CSV to MinIO")


def main() -> None:
    ingestor = ERPIngestor()

    while True:
        try:
            ingestor.run_once()
        except Exception:
            logger.exception("Ingest cycle failed")
        logger.info("Sleeping %ds until next ingest cycle", INGEST_INTERVAL)
        time.sleep(INGEST_INTERVAL)


if __name__ == "__main__":
    main()
