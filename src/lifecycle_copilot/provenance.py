from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .events import utc_now


@dataclass
class ProvenanceLedger:
    path: Path

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")

    def append(
        self,
        *,
        stage: str,
        iteration: int,
        failure: str,
        diagnosis: str,
        patch: str,
        rationale: str,
        validation_result: str,
        **extra: Any,
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "stage": stage,
            "iteration": iteration,
            "failure": failure,
            "diagnosis": diagnosis,
            "patch": patch,
            "rationale": rationale,
            "validation_result": validation_result,
            "timestamp": utc_now(),
        }
        entry.update(extra)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
        return entry
