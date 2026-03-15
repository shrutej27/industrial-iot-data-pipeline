# Sensor Simulator

MQTT sensor publisher that simulates 3–5 factory machines with realistic distributions.

## Topics

- `factory/machine-{id}/temperature`
- `factory/machine-{id}/rpm`
- `factory/machine-{id}/pressure`

## Message Schema

```json
{
  "machine_id": "machine-1",
  "metric": "temperature",
  "value": 78.3,
  "unit": "°C",
  "timestamp": "2026-03-14T12:00:00Z"
}
```
