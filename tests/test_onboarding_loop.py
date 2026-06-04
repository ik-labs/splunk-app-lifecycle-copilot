import json
from pathlib import Path

from lifecycle_copilot.onboarding.loop import OnboardingLoop
from lifecycle_copilot.onboarding.mcp_client import McpPreflight, McpQueryResponse

from test_onboarding_validator import robust_rows


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_onboarding_loop_heals_with_fake_mcp_and_hec(tmp_path: Path) -> None:
    log_file = tmp_path / "sample_upi.log"
    log_file.write_text("\n".join(row["_raw"] for row in robust_rows()) + "\n", encoding="utf-8")
    fake_hec = _FakeHecIngestor()
    fake_mcp = _FakeMcpClient()

    result = OnboardingLoop(
        log_file=log_file,
        run_dir=tmp_path / "onboarding-run",
        max_iters=3,
        mcp_client=fake_mcp,
        hec_ingestor=fake_hec,
    ).run()

    assert result.status == "clean"
    assert result.iterations == 1
    assert result.ingested_count == 2
    assert result.initial_summary["failure"] > 0
    assert result.final_summary["failure"] == 0
    assert (result.run_dir / "onboarding" / "candidate-00.spl").exists()
    assert (result.run_dir / "onboarding" / "candidate-01.spl").exists()
    assert (result.run_dir / "onboarding" / "validation-00.json").exists()
    assert (result.run_dir / "onboarding" / "validation-01.json").exists()

    events = read_jsonl(result.run_dir / "events.jsonl")
    event_types = {event["type"] for event in events}
    assert {
        "run_started",
        "mcp_tool_call",
        "failure_detected",
        "diagnosis",
        "patch_applied",
        "revalidated",
        "field_extracted",
        "pii_flagged",
        "ledger_entry",
        "run_complete",
    }.issubset(event_types)
    assert sum(1 for event in events if event["type"] == "field_extracted") == 6
    assert sum(1 for event in events if event["type"] == "pii_flagged") == 2
    assert (result.run_dir / "events.json").exists()
    assert len(read_jsonl(result.run_dir / "provenance.jsonl")) == 1

    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert summary["mcp_preflight"]["query_argument"] == "query"
    assert fake_hec.ingested == 2


class _FakeMcpClient:
    def preflight(self) -> McpPreflight:
        return McpPreflight(
            tool_names=("splunk_run_query",),
            run_query_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            query_argument="query",
        )

    def run_query(self, spl: str) -> McpQueryResponse:
        if "pii_payer_mobile=if" in spl:
            return McpQueryResponse(rows=robust_rows(), raw_payload={"rows": robust_rows()})
        return McpQueryResponse(
            rows=[
                {
                    "_raw": robust_rows()[0]["_raw"],
                    "event_time": "2026-06-02T10:03:52+05:30",
                    "txn_id": "UPI1",
                }
            ],
            raw_payload={"rows": "naive"},
        )


class _FakeHecIngestor:
    def __init__(self) -> None:
        self.ingested = 0

    def ingest_lines(self, lines) -> int:
        materialized = list(lines)
        self.ingested = len(materialized)
        return self.ingested
