from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    description: str
    spl: str


@dataclass(frozen=True)
class OnboardingFailure:
    failure_id: str
    check: str
    file: str | None
    line: int | None
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CandidateValidation:
    candidate_id: str
    rows: tuple[dict[str, Any], ...]
    summary: dict[str, Any]
    failures: tuple[OnboardingFailure, ...]
    report_path: Path
    extracted_mappings: tuple[dict[str, str], ...] = ()
    pii_fields: tuple[str, ...] = ()
