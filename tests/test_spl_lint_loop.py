import json
from pathlib import Path

from lifecycle_copilot.spl_lint.loop import SplLintLoop
from lifecycle_copilot.spl_lint.rules import lint_spl


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_QUERY = REPO_ROOT / "fixtures" / "spl_lint" / "costly_search.spl"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_spl_lint_loop_heals_fixture_without_mutating_source(tmp_path: Path) -> None:
    source_before = FIXTURE_QUERY.read_text(encoding="utf-8")
    assert len(lint_spl(source_before)) == 3

    result = SplLintLoop(
        source_query=FIXTURE_QUERY,
        run_dir=tmp_path / "spl-lint-run",
        max_iters=5,
    ).run()

    assert result.status == "clean"
    assert result.iterations == 3
    assert result.initial_summary["failure"] == 3
    assert result.final_summary["failure"] == 0

    # Source fixture is untouched; only the working copy is rewritten.
    assert FIXTURE_QUERY.read_text(encoding="utf-8") == source_before
    healed = result.work_query.read_text(encoding="utf-8")
    assert lint_spl(healed) == []
    assert "index=main" in healed
    assert "earliest=-24h" in healed
    assert "| sort 1000 -_time" in healed

    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "clean"
    assert lint_spl(summary["final_query"]) == []

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
    assert [entry["check"] for entry in ledger_entries] == [
        "spl_wildcard_index",
        "spl_all_time",
        "spl_unbounded_sort",
    ]
