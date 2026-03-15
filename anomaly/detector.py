"""Z-score anomaly detector — queries InfluxDB, flags |Z| > threshold, writes to anomalies measurement."""

import logging
import os
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("anomaly-detector")

# ── Configuration ────────────────────────────────────────────────────────────
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
INFLUXDB_TOKEN = os.environ["INFLUXDB_TOKEN"]
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "factory")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "iot")

INTERVAL = int(os.getenv("ANOMALY_INTERVAL_SECONDS", "60"))
Z_THRESHOLD = float(os.getenv("ANOMALY_Z_THRESHOLD", "3.0"))
WINDOW_MINUTES = int(os.getenv("ANOMALY_WINDOW_MINUTES", "10"))


class AnomalyDetector:
    """Queries recent sensor_readings, computes rolling Z-scores, writes anomalies back."""

    def __init__(self) -> None:
        self._client = InfluxDBClient(
            url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG
        )
        self._query_api = self._client.query_api()
        self._write_api = self._client.write_api(write_options=SYNCHRONOUS)

    def detect(self) -> int:
        """Run one detection cycle. Returns count of anomalies found."""
        query = f"""
        from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: -{WINDOW_MINUTES}m)
            |> filter(fn: (r) => r._measurement == "sensor_readings")
            |> filter(fn: (r) => r._field == "value")
            |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
        """
        try:
            tables = self._query_api.query_data_frame(query)
        except Exception:
            logger.exception("Failed to query InfluxDB")
            return 0

        if isinstance(tables, list):
            df = pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()
        else:
            df = tables

        if df.empty or "value" not in df.columns:
            logger.info("No sensor data in last %d minutes", WINDOW_MINUTES)
            return 0

        anomaly_count = 0
        points: list[Point] = []
        now = datetime.now(timezone.utc)

        for (mid, metric), group in df.groupby(["machine_id", "metric"]):
            values = group["value"].dropna()
            if len(values) < 3:
                continue

            mean = values.mean()
            std = values.std()
            if std == 0:
                continue

            z_scores = (values - mean) / std
            anomalies = values[np.abs(z_scores) > Z_THRESHOLD]

            for val in anomalies:
                z = float((val - mean) / std)
                points.append(
                    Point("anomalies")
                    .tag("machine_id", str(mid))
                    .tag("metric", str(metric))
                    .field("value", float(val))
                    .field("z_score", z)
                    .field("mean", float(mean))
                    .field("std", float(std))
                    .time(now, WritePrecision.S)
                )
                anomaly_count += 1

        if points:
            try:
                self._write_api.write(bucket=INFLUXDB_BUCKET, record=points)
                logger.warning(
                    "Detected %d anomalies, written to InfluxDB", anomaly_count
                )
            except Exception:
                logger.exception("Failed to write anomalies to InfluxDB")
        else:
            logger.info("No anomalies detected in last %d minutes", WINDOW_MINUTES)

        return anomaly_count


def main() -> None:
    detector = AnomalyDetector()
    logger.info(
        "Anomaly detector started (interval=%ds, Z>%.1f, window=%dm)",
        INTERVAL,
        Z_THRESHOLD,
        WINDOW_MINUTES,
    )

    while True:
        try:
            detector.detect()
        except Exception:
            logger.exception("Detection cycle failed")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
