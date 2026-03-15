# Anomaly Detector

Z-score based anomaly detection service. Queries InfluxDB for recent readings, computes rolling statistics, and flags anomalies.

## Configuration

- `ANOMALY_INTERVAL_SECONDS` — polling interval (default: 60)
- `ANOMALY_Z_THRESHOLD` — Z-score threshold (default: 3.0)
- `ANOMALY_WINDOW_MINUTES` — lookback window (default: 10)
