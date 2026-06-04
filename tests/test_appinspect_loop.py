import json
from pathlib import Path

from lifecycle_copilot.appinspect.loop import AppInspectLoop
from lifecycle_copilot.appinspect.runner import AppInspectRunner


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_APP = REPO_ROOT / "fixtures" / "appinspect" / "broken_app"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_appinspect_loop_heals_fixture_without_mutating_source(tmp_path: Path) -> None:
    runner = AppInspectRunner()
    baseline = runner.inspect(FIXTURE_APP, tmp_path / "baseline.json", iteration=0)
    assert baseline.summary["failure"] == 3

    fixture_paths = [
        FIXTURE_APP / "local" / "app.conf",
        FIXTURE_APP / "default" / "user-seed.conf",
        FIXTURE_APP / "default" / "outputs.conf",
    ]
    assert all(path.exists() for path in fixture_paths)

    result = AppInspectLoop(
        source_app=FIXTURE_APP,
        run_dir=tmp_path / "appinspect-run",
        max_iters=5,
    ).run()

    assert result.status == "clean"
    assert result.iterations == 3
    assert result.initial_summary["failure"] == 3
    assert result.final_summary["failure"] == 0
    assert all(path.exists() for path in fixture_paths)
    assert not (result.work_app / "local").exists()
    assert not (result.work_app / "default" / "user-seed.conf").exists()
    assert not (result.work_app / "default" / "outputs.conf").exists()

    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "clean"
    assert Path(summary["final_report"]).exists()

    events = read_jsonl(result.run_dir / "events.jsonl")
    event_types = {event["type"] for event in events}
    assert {
        "run_started",
        "failure_detected",
        "diagnosis",
        "patch_applied",
        "revalidated",
        "ledger_entry",
        "run_complete",
    }.issubset(event_types)
    assert (result.run_dir / "events.json").exists()

    ledger_entries = read_jsonl(result.run_dir / "provenance.jsonl")
    assert len(ledger_entries) == 3
    assert {entry["validation_result"] for entry in ledger_entries} == {"pass"}
