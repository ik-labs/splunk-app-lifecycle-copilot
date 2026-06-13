from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from lifecycle_copilot.diagnosis import TemplateDiagnosisProvider
from lifecycle_copilot.events import EventRecorder
from lifecycle_copilot.provenance import ProvenanceLedger
from lifecycle_copilot.self_heal import SelfHealEngine, SelfHealRunResult, ValidationResult

from .patchers import apply_appinspect_patch, select_appinspect_failure
from .runner import AppInspectRunner


@dataclass(frozen=True)
class AppInspectLoopResult:
    status: str
    iterations: int
    run_dir: Path
    work_app: Path
    initial_summary: dict[str, Any]
    final_summary: dict[str, Any]
    summary_path: Path


class AppInspectLoop:
    def __init__(
        self,
        *,
        source_app: Path,
        run_dir: Path,
        max_iters: int = 5,
        appinspect_binary: str | None = None,
        event_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.source_app = Path(source_app)
        self.run_dir = Path(run_dir)
        self.max_iters = max_iters
        self.runner = AppInspectRunner(appinspect_binary)
        self.event_sink = event_sink

    def run(self) -> AppInspectLoopResult:
        if not self.source_app.is_dir():
            raise FileNotFoundError(f"AppInspect source app does not exist: {self.source_app}")
        if self.run_dir.exists():
            raise FileExistsError(f"Run directory already exists: {self.run_dir}")

        work_root = self.run_dir / "work"
        appinspect_dir = self.run_dir / "appinspect"
        work_app = work_root / self.source_app.name
        appinspect_dir.mkdir(parents=True)
        shutil.copytree(self.source_app, work_app)

        events = EventRecorder(self.run_dir, on_event=self.event_sink)
        ledger = ProvenanceLedger(self.run_dir / "provenance.jsonl")
        diagnosis_provider = TemplateDiagnosisProvider()

        def validate(iteration: int) -> ValidationResult:
            report_path = appinspect_dir / f"iteration-{iteration:02d}.json"
            run = self.runner.inspect(work_app, report_path, iteration=iteration)
            return ValidationResult(
                iteration=iteration,
                failures=run.failures,
                summary=dict(run.summary),
                report_path=run.report_path,
            )

        engine = SelfHealEngine(
            stage="appinspect",
            validate=validate,
            select_failure=select_appinspect_failure,
            diagnose=diagnosis_provider.diagnose,
            apply_patch=lambda failure: apply_appinspect_patch(work_app, failure),
            events=events,
            ledger=ledger,
            max_iters=self.max_iters,
        )
        engine_result = engine.run()
        return self._write_summary(engine_result, work_app)

    def _write_summary(self, result: SelfHealRunResult, work_app: Path) -> AppInspectLoopResult:
        summary_path = self.run_dir / "summary.json"
        initial_summary = result.validations[0].summary
        final_summary = result.final_validation.summary
        summary = {
            "status": result.status,
            "iterations": result.iterations,
            "source_app": str(self.source_app),
            "work_app": str(work_app),
            "initial_summary": initial_summary,
            "final_summary": final_summary,
            "final_report": str(result.final_validation.report_path),
            "events_jsonl": str(self.run_dir / "events.jsonl"),
            "events_json": str(self.run_dir / "events.json"),
            "provenance_jsonl": str(self.run_dir / "provenance.jsonl"),
        }
        summary_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2) + "\n")
        return AppInspectLoopResult(
            status=result.status,
            iterations=result.iterations,
            run_dir=self.run_dir,
            work_app=work_app,
            initial_summary=initial_summary,
            final_summary=final_summary,
            summary_path=summary_path,
        )
