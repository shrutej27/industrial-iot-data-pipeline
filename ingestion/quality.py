"""Data quality checks for ERP CSV records — detects missing values, out-of-range, duplicates."""

import logging
from datetime import datetime

import pandas as pd
import psycopg2

from models import ERPRecord, QualityIssue

logger = logging.getLogger("quality")


class QualityChecker:
    """Runs quality checks on a DataFrame of raw ERP rows and logs issues to PostgreSQL."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    # ── Public entry point ───────────────────────────────────────────────
    def check(self, df: pd.DataFrame) -> tuple[list[ERPRecord], list[QualityIssue]]:
        """Return (valid_records, issues) after running all quality checks."""
        issues: list[QualityIssue] = []
        valid: list[ERPRecord] = []

        # 1. Duplicate detection
        dup_mask = df.duplicated(subset=["machine_id", "production_date"], keep="first")
        for idx in df.index[dup_mask]:
            row = df.loc[idx]
            issues.append(
                QualityIssue(
                    source="erp_csv",
                    record_id=str(idx),
                    issue_type="duplicate",
                    details=f"Duplicate row for {row['machine_id']} on {row['production_date']}",
                )
            )
        df_deduped = df[~dup_mask]

        # 2. Row-level validation
        for idx, row in df_deduped.iterrows():
            row_issues = self._validate_row(idx, row)
            if row_issues:
                issues.extend(row_issues)
            else:
                valid.append(ERPRecord(**row.to_dict()))

        # 3. Persist issues
        if issues:
            self._write_issues(issues)
            logger.warning("Found %d quality issues", len(issues))

        return valid, issues

    # ── Row Validation ───────────────────────────────────────────────────
    def _validate_row(self, idx: int, row: pd.Series) -> list[QualityIssue]:
        issues: list[QualityIssue] = []

        # Missing values
        for col in ["machine_id", "production_date", "units_produced", "energy_kwh"]:
            if pd.isna(row.get(col)):
                issues.append(
                    QualityIssue(
                        source="erp_csv",
                        record_id=str(idx),
                        issue_type="missing_value",
                        field_name=col,
                        details=f"Missing required field '{col}'",
                    )
                )

        # Out-of-range checks
        if not pd.isna(row.get("defect_count")) and int(row["defect_count"]) < 0:
            issues.append(
                QualityIssue(
                    source="erp_csv",
                    record_id=str(idx),
                    issue_type="out_of_range",
                    field_name="defect_count",
                    details=f"Negative defect_count: {row['defect_count']}",
                )
            )

        if not pd.isna(row.get("energy_kwh")) and float(row["energy_kwh"]) < 0:
            issues.append(
                QualityIssue(
                    source="erp_csv",
                    record_id=str(idx),
                    issue_type="out_of_range",
                    field_name="energy_kwh",
                    details=f"Negative energy_kwh: {row['energy_kwh']}",
                )
            )

        # Pydantic full validation if no fatal issues yet
        if not issues:
            try:
                ERPRecord(**row.to_dict())
            except Exception as e:
                issues.append(
                    QualityIssue(
                        source="erp_csv",
                        record_id=str(idx),
                        issue_type="validation_error",
                        details=str(e),
                    )
                )
        return issues

    # ── Persist issues to PostgreSQL ─────────────────────────────────────
    def _write_issues(self, issues: list[QualityIssue]) -> None:
        try:
            conn = psycopg2.connect(self._dsn)
            with conn:
                with conn.cursor() as cur:
                    for issue in issues:
                        cur.execute(
                            """INSERT INTO data_quality_log
                               (source, record_id, issue_type, field_name, details, detected_at)
                               VALUES (%s, %s, %s, %s, %s, %s)""",
                            (
                                issue.source,
                                issue.record_id,
                                issue.issue_type,
                                issue.field_name,
                                issue.details,
                                issue.detected_at,
                            ),
                        )
            conn.close()
        except Exception:
            logger.exception("Failed to write quality issues to PostgreSQL")
