from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from .diagnosis import Diagnosis
from .events import EventRecorder
from .provenance import ProvenanceLedger


@dataclass(frozen=True)
class ValidationResult:
    iteration: int
    failures: Sequence[Any]
    summary: dict[str, Any]
    report_path: Path | None = None

    @property
    def is_clean(self) -> bool:
        return int(self.summary.get("failure", len(self.failures)) or 0) == 0 and int(
            self.summary.get("error", 0) or 0
        ) == 0


@dataclass(frozen=True)
class PatchResult:
    patch_id: str
    summary: str
    changed_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class SelfHealRunResult:
    status: str
    iterations: int
    validations: tuple[ValidationResult, ...]

    @property
    def final_validation(self) -> ValidationResult:
        return self.validations[-1]


class SelfHealEngine:
    def __init__(
        self,
        *,
        stage: str,
        validate: Callable[[int], ValidationResult],
        select_failure: Callable[[Sequence[Any]], Any],
        diagnose: Callable[[Any], Diagnosis],
        apply_patch: Callable[[Any], PatchResult],
        events: EventRecorder,
        ledger: ProvenanceLedger,
        max_iters: int = 5,
    ) -> None:
        self.stage = stage
        self.validate = validate
        self.select_failure = select_failure
        self.diagnose = diagnose
        self.apply_patch = apply_patch
        self.events = events
        self.ledger = ledger
        self.max_iters = max_iters

    def run(self) -> SelfHealRunResult:
        validations: list[ValidationResult] = []
        self.events.emit("run_started", loop=self.stage)

        validation = self.validate(0)
        validations.append(validation)
        self._emit_failures(validation)

        if validation.is_clean:
            return self._complete("clean", 0, validations)

        for iteration in range(1, self.max_iters + 1):
            if not validation.failures:
                return self._complete("capped", iteration - 1, validations)

            failure = self.select_failure(validation.failures)
            failure_payload = self._failure_payload(failure)
            diagnosis = self.diagnose(failure)

            self.events.emit(
                "diagnosis",
                **failure_payload,
                text=diagnosis.text,
            )

            patch_result = self.apply_patch(failure)
            self.events.emit(
                "patch_applied",
                **failure_payload,
                summary=patch_result.summary,
            )

            validation = self.validate(iteration)
            validations.append(validation)
            remaining_failure_ids = {
                str(getattr(current_failure, "failure_id", ""))
                for current_failure in validation.failures
            }
            revalidation_result = (
                "fail" if failure_payload["failure_id"] in remaining_failure_ids else "pass"
            )

            self.events.emit(
                "revalidated",
                **failure_payload,
                result=revalidation_result,
                iteration=iteration,
            )

            ledger_entry = self.ledger.append(
                stage=self.stage,
                iteration=iteration,
                failure=self._failure_label(failure),
                diagnosis=diagnosis.text,
                patch=patch_result.summary,
                rationale=diagnosis.rationale,
                validation_result=revalidation_result,
                failure_id=failure_payload["failure_id"],
                check=failure_payload["check"],
                file=failure_payload["file"],
                line=failure_payload["line"],
                message=failure_payload["message"],
                changed_paths=list(patch_result.changed_paths),
            )
            self.events.emit(
                "ledger_entry",
                stage=self.stage,
                iteration=iteration,
                failure=ledger_entry["failure"],
                diagnosis=diagnosis.text,
                patch=patch_result.summary,
                rationale=diagnosis.rationale,
                result=revalidation_result,
                failure_id=failure_payload["failure_id"],
                message=failure_payload["message"],
            )

            self._emit_failures(validation)
            if validation.is_clean:
                return self._complete("clean", iteration, validations)

        return self._complete("capped", self.max_iters, validations)

    def _complete(
        self,
        status: str,
        iterations: int,
        validations: list[ValidationResult],
    ) -> SelfHealRunResult:
        self.events.emit(
            "run_complete",
            loop=self.stage,
            status=status,
            iterations=iterations,
        )
        self.events.write_snapshot()
        return SelfHealRunResult(
            status=status,
            iterations=iterations,
            validations=tuple(validations),
        )

    def _emit_failures(self, validation: ValidationResult) -> None:
        for failure in validation.failures:
            self.events.emit(
                "failure_detected",
                loop=self.stage,
                **self._failure_payload(failure),
            )

    @staticmethod
    def _failure_payload(failure: Any) -> dict[str, Any]:
        return {
            "failure_id": str(getattr(failure, "failure_id", "")),
            "check": getattr(failure, "check", None),
            "file": getattr(failure, "file", None),
            "line": getattr(failure, "line", None),
            "message": getattr(failure, "message", None),
        }

    @staticmethod
    def _failure_label(failure: Any) -> str:
        check = getattr(failure, "check", "unknown_check")
        file = getattr(failure, "file", None) or "app"
        return f"{check} ({file})"
