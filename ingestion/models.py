"""Pydantic v2 validation models for sensor readings, ERP records, and quality issues."""

from datetime import date, datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class SensorReading(BaseModel):
    """Validates a single MQTT sensor reading."""

    machine_id: str = Field(..., pattern=r"^machine-\d+$")
    metric: str = Field(..., pattern=r"^(temperature|rpm|pressure)$")
    value: float
    unit: str
    timestamp: str

    @field_validator("value")
    @classmethod
    def value_within_physical_range(cls, v: float, info) -> float:
        metric = info.data.get("metric")
        ranges = {
            "temperature": (-40.0, 200.0),
            "rpm": (0.0, 5000.0),
            "pressure": (0.0, 20.0),
        }
        if metric and metric in ranges:
            lo, hi = ranges[metric]
            if not (lo <= v <= hi):
                raise ValueError(f"{metric} value {v} out of physical range [{lo}, {hi}]")
        return v


class ERPRecord(BaseModel):
    """Validates a single ERP production record from CSV."""

    machine_id: str = Field(..., pattern=r"^machine-\d+$")
    production_date: date
    units_produced: int = Field(..., ge=0)
    energy_kwh: float = Field(..., ge=0.0)
    defect_count: int = Field(..., ge=0)
    operator: Optional[str] = None
    shift: Optional[str] = Field(None, pattern=r"^(morning|afternoon|night)$")


class QualityIssue(BaseModel):
    """Represents a single data-quality finding."""

    source: str
    record_id: Optional[str] = None
    issue_type: str
    field_name: Optional[str] = None
    details: str
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
