from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .candidates import CIM_MAPPINGS, PII_FIELDS, RAW_FIELDS
from .models import Candidate, CandidateValidation, OnboardingFailure


TIMESTAMP_PATTERN = re.compile(r"^(?:\d{13}|\d{4}-\d{2}-\d{2}T\S+)")
FIELD_PATTERN_TEMPLATE = r"(?:^|\s){field}=(?P<value>\S+)"


def validate_candidate_rows(
    *,
    candidate: Candidate,
    rows: list[dict[str, Any]],
    report_path: Path,
) -> CandidateValidation:
    normalized_rows = tuple(dict(row) for row in rows)
    failures: list[OnboardingFailure] = []

    field_coverage = _field_coverage(normalized_rows)
    missing_fields = [
        name
        for name, coverage in field_coverage.items()
        if coverage["expected"] > coverage["extracted"]
    ]
    if not normalized_rows:
        missing_fields = list(RAW_FIELDS)

    if missing_fields:
        failures.append(
            OnboardingFailure(
                failure_id=f"onboarding:{candidate.candidate_id}:field_coverage_gap",
                check="field_coverage_gap",
                file=f"{candidate.candidate_id}.spl",
                line=None,
                message=(
                    "Candidate did not extract all expected key/value fields: "
                    + ", ".join(missing_fields)
                ),
                details={"missing_fields": missing_fields, "coverage": field_coverage},
            )
        )

    timestamp_coverage = _timestamp_coverage(normalized_rows)
    if timestamp_coverage["expected"] > timestamp_coverage["extracted"]:
        failures.append(
            OnboardingFailure(
                failure_id=f"onboarding:{candidate.candidate_id}:timestamp_coverage_gap",
                check="timestamp_coverage_gap",
                file=f"{candidate.candidate_id}.spl",
                line=None,
                message=(
                    "Candidate did not handle both timestamp formats: "
                    f"{timestamp_coverage['extracted']}/{timestamp_coverage['expected']} extracted"
                ),
                details={"coverage": timestamp_coverage},
            )
        )

    cim_coverage = _cim_coverage(normalized_rows)
    missing_mappings = [
        f"{raw}->{alias}"
        for raw, alias in CIM_MAPPINGS
        if cim_coverage[f"{raw}->{alias}"]["expected"]
        > cim_coverage[f"{raw}->{alias}"]["extracted"]
    ]
    if missing_mappings:
        failures.append(
            OnboardingFailure(
                failure_id=f"onboarding:{candidate.candidate_id}:cim_mapping_gap",
                check="cim_mapping_gap",
                file=f"{candidate.candidate_id}.spl",
                line=None,
                message="Candidate did not populate required CIM aliases: "
                + ", ".join(missing_mappings),
                details={"missing_mappings": missing_mappings, "coverage": cim_coverage},
            )
        )

    pii_coverage = _pii_coverage(normalized_rows)
    missing_pii = [
        name
        for name, coverage in pii_coverage.items()
        if coverage["expected"] > coverage["flagged"]
    ]
    if missing_pii:
        failures.append(
            OnboardingFailure(
                failure_id=f"onboarding:{candidate.candidate_id}:pii_flag_gap",
                check="pii_flag_gap",
                file=f"{candidate.candidate_id}.spl",
                line=None,
                message="Candidate did not flag required PII fields: " + ", ".join(missing_pii),
                details={"missing_pii": missing_pii, "coverage": pii_coverage},
            )
        )

    summary: dict[str, Any] = {
        "failure": len(failures),
        "error": 0,
        "candidate_id": candidate.candidate_id,
        "row_count": len(normalized_rows),
        "field_coverage": field_coverage,
        "timestamp_coverage": timestamp_coverage,
        "cim_coverage": cim_coverage,
        "pii_coverage": pii_coverage,
    }
    report = {
        "candidate_id": candidate.candidate_id,
        "candidate_description": candidate.description,
        "summary": summary,
        "failures": [_failure_to_dict(failure) for failure in failures],
        "rows": list(normalized_rows),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    extracted_mappings = ()
    pii_fields = ()
    if not failures:
        extracted_mappings = tuple({"raw": raw, "cim": alias} for raw, alias in CIM_MAPPINGS)
        pii_fields = tuple(PII_FIELDS)

    return CandidateValidation(
        candidate_id=candidate.candidate_id,
        rows=normalized_rows,
        summary=summary,
        failures=tuple(failures),
        report_path=report_path,
        extracted_mappings=extracted_mappings,
        pii_fields=pii_fields,
    )


def _field_coverage(rows: tuple[dict[str, Any], ...]) -> dict[str, dict[str, int]]:
    coverage: dict[str, dict[str, int]] = {}
    for field in RAW_FIELDS:
        expected = sum(1 for row in rows if _raw_field_value(row, field))
        extracted = sum(1 for row in rows if _present(row.get(field)))
        coverage[field] = {"expected": expected, "extracted": extracted}
    return coverage


def _timestamp_coverage(rows: tuple[dict[str, Any], ...]) -> dict[str, int]:
    expected = sum(1 for row in rows if TIMESTAMP_PATTERN.search(str(row.get("_raw", ""))))
    extracted = sum(1 for row in rows if _present(row.get("event_time")))
    return {"expected": expected, "extracted": extracted}


def _cim_coverage(rows: tuple[dict[str, Any], ...]) -> dict[str, dict[str, int]]:
    coverage: dict[str, dict[str, int]] = {}
    for raw, alias in CIM_MAPPINGS:
        expected = sum(1 for row in rows if _raw_field_value(row, raw))
        extracted = sum(1 for row in rows if _present(row.get(alias)))
        coverage[f"{raw}->{alias}"] = {"expected": expected, "extracted": extracted}
    return coverage


def _pii_coverage(rows: tuple[dict[str, Any], ...]) -> dict[str, dict[str, int]]:
    coverage: dict[str, dict[str, int]] = {}
    for field in PII_FIELDS:
        expected = sum(1 for row in rows if _raw_field_value(row, field))
        flag_field = f"pii_{field}"
        flagged = sum(1 for row in rows if _raw_field_value(row, field) and _present(row.get(flag_field)))
        coverage[field] = {"expected": expected, "flagged": flagged}
    return coverage


def _raw_field_value(row: dict[str, Any], field: str) -> str | None:
    pattern = re.compile(FIELD_PATTERN_TEMPLATE.format(field=re.escape(field)))
    match = pattern.search(str(row.get("_raw", "")))
    if not match:
        return None
    value = match.group("value")
    return value if value else None


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list | tuple | set):
        return bool(value)
    return True


def _failure_to_dict(failure: OnboardingFailure) -> dict[str, Any]:
    return {
        "failure_id": failure.failure_id,
        "check": failure.check,
        "file": failure.file,
        "line": failure.line,
        "message": failure.message,
        "details": failure.details,
    }
