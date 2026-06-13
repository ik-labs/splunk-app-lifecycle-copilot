from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from lifecycle_copilot.events import EventRecorder
from lifecycle_copilot.provenance import ProvenanceLedger
from lifecycle_copilot.self_heal import SelfHealEngine, SelfHealRunResult, ValidationResult

from .patchers import apply_spl_patch, select_spl_finding
from .rules import diagnose_spl, lint_spl


@dataclass(frozen=True)
class SplLintLoopResult:
    status: str
    iterations: int
    run_dir: Path
    work_query: Path
    initial_summary: dict[str, Any]
    final_summary: dict[str, Any]
    summary_path: Path


class SplLintLoop:
    """Cost-aware SPL lint loop on the shared self-heal engine.

    Static analysis only — like the AppInspect loop, it needs no running
    Splunk. A deliberately costly query is linted, each finding is healed by a
    deterministic rewrite, and the search is re-linted until it is clean.
    """

    def __init__(
        self,
        *,
        source_query: Path,
        run_dir: Path,
        max_iters: int = 5,
        event_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.source_query = Path(source_query)
        self.run_dir = Path(run_dir)
        self.max_iters = max_iters
        self.event_sink = event_sink

    def run(self) -> SplLintLoopResult:
        if not self.source_query.is_file():
            raise FileNotFoundError(f"SPL source query does not exist: {self.source_query}")
        if self.run_dir.exists():
            raise FileExistsError(f"Run directory already exists: {self.run_dir}")

        work_root = self.run_dir / "work"
        report_dir = self.run_dir / "spl"
        work_query = work_root / self.source_query.name
        report_dir.mkdir(parents=True)
        work_root.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.source_query, work_query)

        events = EventRecorder(self.run_dir, on_event=self.event_sink)
        ledger = ProvenanceLedger(self.run_dir / "provenance.jsonl")

        def validate(iteration: int) -> ValidationResult:
            text = work_query.read_text()
            findings = lint_spl(text, file=work_query.name)
            report_path = report_dir / f"iteration-{iteration:02d}.json"
            report = {
                "iteration": iteration,
                "summary": {"failure": len(findings), "error": 0},
                "query": text,
                "findings": [
                    {
                        "failure_id": finding.failure_id,
                        "check": finding.check,
                        "file": finding.file,
                        "line": finding.line,
                        "message": finding.message,
                    }
                    for finding in findings
                ],
            }
            report_path.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n")
            return ValidationResult(
                iteration=iteration,
                failures=findings,
                summary=report["summary"],
                report_path=report_path,
            )

        def apply_patch(finding: Any) -> Any:
            text = work_query.read_text()
            new_text, result = apply_spl_patch(text, finding)
            work_query.write_text(new_text)
            return result

        engine = SelfHealEngine(
            stage="spl_lint",
            validate=validate,
            select_failure=select_spl_finding,
            diagnose=diagnose_spl,
            apply_patch=apply_patch,
            events=events,
            ledger=ledger,
            max_iters=self.max_iters,
        )
        engine_result = engine.run()
        return self._write_summary(engine_result, work_query)

    def _write_summary(
        self, result: SelfHealRunResult, work_query: Path
    ) -> SplLintLoopResult:
        summary_path = self.run_dir / "summary.json"
        initial_summary = result.validations[0].summary
        final_summary = result.final_validation.summary
        summary = {
            "status": result.status,
            "iterations": result.iterations,
            "source_query": str(self.source_query),
            "work_query": str(work_query),
            "initial_summary": initial_summary,
            "final_summary": final_summary,
            "final_query": work_query.read_text(),
            "events_jsonl": str(self.run_dir / "events.jsonl"),
            "events_json": str(self.run_dir / "events.json"),
            "provenance_jsonl": str(self.run_dir / "provenance.jsonl"),
        }
        summary_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2) + "\n")
        return SplLintLoopResult(
            status=result.status,
            iterations=result.iterations,
            run_dir=self.run_dir,
            work_query=work_query,
            initial_summary=initial_summary,
            final_summary=final_summary,
            summary_path=summary_path,
        )
