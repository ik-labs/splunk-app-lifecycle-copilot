from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lifecycle_copilot.diagnosis import Diagnosis, DiagnosisProvider
from lifecycle_copilot.events import EventRecorder
from lifecycle_copilot.provenance import ProvenanceLedger
from lifecycle_copilot.self_heal import SelfHealEngine, SelfHealRunResult, ValidationResult

from .candidates import get_candidate
from .hec import HecIngestor
from .mcp_client import (
    RUN_QUERY_TOOL,
    McpQueryResponse,
    McpSplunkClient,
    McpToolSchemaError,
    McpToolUnavailableError,
)
from .models import Candidate, CandidateValidation
from .patchers import CandidateState, apply_onboarding_patch, select_onboarding_failure
from .validator import validate_candidate_rows


@dataclass(frozen=True)
class OnboardingLoopResult:
    status: str
    iterations: int
    run_dir: Path
    run_id: str
    splunk_source: str
    ingested_count: int
    initial_summary: dict[str, Any]
    final_summary: dict[str, Any]
    summary_path: Path


class OnboardingDiagnosisProvider(DiagnosisProvider):
    _TEMPLATES = {
        "field_coverage_gap": Diagnosis(
            text=(
                "The positional extraction misses fields when the UPI fixture changes "
                "field order or omits optional keys."
            ),
            rationale=(
                "Switch to independent key/value rex clauses so every present key can "
                "extract without depending on neighboring fields."
            ),
        ),
        "timestamp_coverage_gap": Diagnosis(
            text=(
                "The candidate only handles one timestamp shape, but the fixture mixes "
                "ISO-8601 values and epoch milliseconds."
            ),
            rationale=(
                "Use a timestamp expression that accepts either ISO-8601 or a 13-digit "
                "epoch-millisecond prefix."
            ),
        ),
        "cim_mapping_gap": Diagnosis(
            text="The candidate extracts payment-domain names but does not fully populate CIM aliases.",
            rationale="Add deterministic eval aliases for amount, action, dest, src_user, transaction_id, and vendor_id.",
        ),
        "pii_flag_gap": Diagnosis(
            text="The candidate exposes payer identifiers without marking the PII fields.",
            rationale="Add explicit PII flag fields for payer_vpa and payer_mobile whenever those values exist.",
        ),
    }

    def diagnose(self, failure: object) -> Diagnosis:
        check = getattr(failure, "check", "")
        return self._TEMPLATES.get(
            check,
            Diagnosis(
                text=f"Onboarding validation reported {check or 'an unsupported failure'}.",
                rationale="Only deterministic onboarding candidate replacements are allowed.",
            ),
        )


class OnboardingLoop:
    def __init__(
        self,
        *,
        log_file: Path,
        run_dir: Path,
        max_iters: int = 3,
        mcp_client: McpSplunkClient | None = None,
        hec_ingestor: HecIngestor | None = None,
    ) -> None:
        self.log_file = Path(log_file)
        self.run_dir = Path(run_dir)
        self.max_iters = max_iters
        self.mcp_client = mcp_client
        self.hec_ingestor = hec_ingestor
        self.run_id = uuid.uuid4().hex[:12]
        self.splunk_source = f"copilot:onboarding:{self.run_id}"

    def run(self) -> OnboardingLoopResult:
        if not self.log_file.is_file():
            raise FileNotFoundError(f"Onboarding source log does not exist: {self.log_file}")
        if self.run_dir.exists():
            raise FileExistsError(f"Run directory already exists: {self.run_dir}")

        onboarding_dir = self.run_dir / "onboarding"
        onboarding_dir.mkdir(parents=True)
        events = EventRecorder(self.run_dir)
        ledger = ProvenanceLedger(self.run_dir / "provenance.jsonl")

        state = CandidateState()
        emitted_success_events = {"done": False}
        validation_records: list[CandidateValidation] = []
        ingested_count = 0

        try:
            mcp_client = self.mcp_client or McpSplunkClient.from_env()
            preflight = mcp_client.preflight()
            hec_ingestor = self.hec_ingestor or HecIngestor.from_env(source=self.splunk_source)
            ingested_count = hec_ingestor.ingest_lines(
                self.log_file.read_text(encoding="utf-8").splitlines()
            )

            def validate(iteration: int) -> ValidationResult:
                candidate = self._candidate_for_state(state)
                candidate_path = onboarding_dir / f"{candidate.candidate_id}.spl"
                candidate_path.write_text(candidate.spl + "\n", encoding="utf-8")

                events.emit(
                    "mcp_tool_call",
                    loop="onboarding",
                    tool=RUN_QUERY_TOOL,
                    status="started",
                    iteration=iteration,
                    candidate_id=candidate.candidate_id,
                    query_argument=preflight.query_argument,
                )
                try:
                    response = mcp_client.run_query(candidate.spl)
                except Exception as exc:
                    events.emit(
                        "mcp_tool_call",
                        loop="onboarding",
                        tool=RUN_QUERY_TOOL,
                        status="failed",
                        iteration=iteration,
                        candidate_id=candidate.candidate_id,
                        error=str(exc),
                    )
                    raise

                events.emit(
                    "mcp_tool_call",
                    loop="onboarding",
                    tool=RUN_QUERY_TOOL,
                    status="succeeded",
                    iteration=iteration,
                    candidate_id=candidate.candidate_id,
                    rows=len(response.rows),
                )

                validation = self._validate_response(
                    candidate=candidate,
                    response=response,
                    report_path=onboarding_dir / f"validation-{iteration:02d}.json",
                )
                validation_records.append(validation)
                if validation.summary["failure"] == 0 and not emitted_success_events["done"]:
                    self._emit_success_events(events, validation)
                    emitted_success_events["done"] = True
                return ValidationResult(
                    iteration=iteration,
                    failures=validation.failures,
                    summary=validation.summary,
                    report_path=validation.report_path,
                )

            engine = SelfHealEngine(
                stage="onboarding",
                validate=validate,
                select_failure=select_onboarding_failure,
                diagnose=OnboardingDiagnosisProvider().diagnose,
                apply_patch=lambda failure: apply_onboarding_patch(state, failure),
                events=events,
                ledger=ledger,
                max_iters=self.max_iters,
            )
            engine_result = engine.run()
            return self._write_summary(
                engine_result,
                ingested_count=ingested_count,
                validation_records=validation_records,
                preflight={
                    "tool_names": list(preflight.tool_names),
                    "run_query_schema": preflight.run_query_schema,
                    "query_argument": preflight.query_argument,
                },
            )
        except Exception as exc:
            self._write_failure_summary(
                error=exc,
                ingested_count=ingested_count,
                state=state,
            )
            events.write_snapshot()
            raise

    def _candidate_for_state(self, state: CandidateState) -> Candidate:
        return get_candidate(
            state.candidate_id,
            index=self._onboarding_index(),
            sourcetype=self._onboarding_sourcetype(),
            source=self.splunk_source,
        )

    def _validate_response(
        self,
        *,
        candidate: Candidate,
        response: McpQueryResponse,
        report_path: Path,
    ) -> CandidateValidation:
        return validate_candidate_rows(
            candidate=candidate,
            rows=response.rows,
            report_path=report_path,
        )

    def _write_summary(
        self,
        result: SelfHealRunResult,
        *,
        ingested_count: int,
        validation_records: list[CandidateValidation],
        preflight: dict[str, Any],
    ) -> OnboardingLoopResult:
        summary_path = self.run_dir / "summary.json"
        initial_summary = result.validations[0].summary
        final_summary = result.final_validation.summary
        summary = {
            "status": result.status,
            "iterations": result.iterations,
            "run_id": self.run_id,
            "source_log": str(self.log_file),
            "splunk_source": self.splunk_source,
            "splunk_index": self._onboarding_index(),
            "splunk_sourcetype": self._onboarding_sourcetype(),
            "ingested_count": ingested_count,
            "initial_summary": initial_summary,
            "final_summary": final_summary,
            "validations": [str(record.report_path) for record in validation_records],
            "mcp_preflight": preflight,
            "events_jsonl": str(self.run_dir / "events.jsonl"),
            "events_json": str(self.run_dir / "events.json"),
            "provenance_jsonl": str(self.run_dir / "provenance.jsonl"),
        }
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return OnboardingLoopResult(
            status=result.status,
            iterations=result.iterations,
            run_dir=self.run_dir,
            run_id=self.run_id,
            splunk_source=self.splunk_source,
            ingested_count=ingested_count,
            initial_summary=initial_summary,
            final_summary=final_summary,
            summary_path=summary_path,
        )

    def _write_failure_summary(
        self,
        *,
        error: Exception,
        ingested_count: int,
        state: CandidateState,
    ) -> None:
        details: dict[str, Any] = {
            "status": "failed",
            "run_id": self.run_id,
            "source_log": str(self.log_file),
            "splunk_source": self.splunk_source,
            "splunk_index": self._onboarding_index(),
            "splunk_sourcetype": self._onboarding_sourcetype(),
            "ingested_count": ingested_count,
            "active_candidate": state.candidate_id,
            "error_type": type(error).__name__,
            "error": str(error),
        }
        if isinstance(error, McpToolUnavailableError):
            details["observed_tools"] = list(error.tool_names)
        if isinstance(error, McpToolSchemaError):
            details["observed_tools"] = list(error.tool_names)
            details["observed_run_query_schema"] = error.schema
        summary_path = self.run_dir / "summary.json"
        summary_path.write_text(
            json.dumps(details, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _emit_success_events(events: EventRecorder, validation: CandidateValidation) -> None:
        for mapping in validation.extracted_mappings:
            events.emit(
                "field_extracted",
                loop="onboarding",
                candidate_id=validation.candidate_id,
                raw_field=mapping["raw"],
                cim_field=mapping["cim"],
                message=f"Mapped {mapping['raw']} to {mapping['cim']}.",
            )
        for pii_field in validation.pii_fields:
            events.emit(
                "pii_flagged",
                loop="onboarding",
                candidate_id=validation.candidate_id,
                field=pii_field,
                message=f"Flagged {pii_field} as PII.",
            )

    @staticmethod
    def _onboarding_index() -> str:
        return os.getenv("SPLUNK_ONBOARDING_INDEX", "main")

    @staticmethod
    def _onboarding_sourcetype() -> str:
        return os.getenv("SPLUNK_ONBOARDING_SOURCETYPE", "upi_gateway_raw")
