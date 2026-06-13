from __future__ import annotations

import json
from pathlib import Path

from lifecycle_copilot.events import EventRecorder
from lifecycle_copilot.server import LIVE_LOOPS, create_app
from lifecycle_copilot.spl_lint.loop import SplLintLoop


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_QUERY = REPO_ROOT / "fixtures" / "spl_lint" / "costly_search.spl"


def test_event_recorder_streams_to_subscriber(tmp_path: Path) -> None:
    seen: list[dict] = []
    recorder = EventRecorder(tmp_path / "run", on_event=seen.append)
    recorder.emit("run_started", loop="spl_lint")
    recorder.emit("run_complete", loop="spl_lint", status="clean", iterations=0)
    assert [event["type"] for event in seen] == ["run_started", "run_complete"]


def test_event_sink_failure_does_not_break_a_run(tmp_path: Path) -> None:
    def boom(_event: dict) -> None:
        raise RuntimeError("subscriber exploded")

    recorder = EventRecorder(tmp_path / "run", on_event=boom)
    # Streaming is best-effort; a bad subscriber must not raise into the loop.
    event = recorder.emit("run_started", loop="spl_lint")
    assert event["type"] == "run_started"


def test_spl_lint_loop_delivers_live_events(tmp_path: Path) -> None:
    streamed: list[dict] = []
    result = SplLintLoop(
        source_query=FIXTURE_QUERY,
        run_dir=tmp_path / "run",
        event_sink=streamed.append,
    ).run()

    assert result.status == "clean"
    types = [event["type"] for event in streamed]
    assert types[0] == "run_started"
    assert types[-1] == "run_complete"
    assert types.count("patch_applied") == 3
    # The streamed events match exactly what was persisted to events.jsonl.
    persisted = [
        json.loads(line)
        for line in (result.run_dir / "events.jsonl").read_text().splitlines()
        if line
    ]
    assert streamed == persisted


def test_server_app_exposes_stream_route() -> None:
    app = create_app()
    paths = {route.path for route in app.routes}
    assert "/api/stream" in paths
    assert "/api/health" in paths
    assert set(LIVE_LOOPS) == {"appinspect", "spl_lint"}
