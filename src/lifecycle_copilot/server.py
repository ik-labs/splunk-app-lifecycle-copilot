"""Live event-stream server for the dashboard.

Runs one of the static self-heal loops (AppInspect or SPL lint -- neither needs
a live Splunk) in a background thread and streams each event to the browser over
Server-Sent Events as the loop actually executes. The dashboard feeds these
through the same reducer it uses for committed replays, so "live" and "replay"
render identically.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable

from sse_starlette.sse import EventSourceResponse
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .appinspect.loop import AppInspectLoop
from .spl_lint.loop import SplLintLoop

# Loops that are safe to run live on demand: static analysis, no Splunk.
LIVE_LOOPS = ("appinspect", "spl_lint")
DEFAULT_DELAY = 0.6


def _repo_root() -> Path:
    return Path.cwd()


def _run_loop(loop_name: str, run_dir: Path, sink: Callable[[dict[str, Any]], None]) -> None:
    root = _repo_root()
    if loop_name == "spl_lint":
        SplLintLoop(
            source_query=root / "fixtures" / "spl_lint" / "costly_search.spl",
            run_dir=run_dir,
            event_sink=sink,
        ).run()
    else:
        AppInspectLoop(
            source_app=root / "fixtures" / "appinspect" / "broken_app",
            run_dir=run_dir,
            event_sink=sink,
        ).run()


async def stream(request: Request) -> EventSourceResponse:
    loop_name = request.query_params.get("loop", "appinspect")
    if loop_name not in LIVE_LOOPS:
        return JSONResponse(
            {"error": f"unknown loop '{loop_name}'", "available": list(LIVE_LOOPS)},
            status_code=400,
        )
    try:
        delay = max(0.0, float(request.query_params.get("delay", DEFAULT_DELAY)))
    except ValueError:
        delay = DEFAULT_DELAY

    main_loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    run_dir = Path(tempfile.mkdtemp(prefix=f"live-{loop_name}-")) / "run"

    def sink(event: dict[str, Any]) -> None:
        main_loop.call_soon_threadsafe(queue.put_nowait, event)

    def worker() -> None:
        try:
            _run_loop(loop_name, run_dir, sink)
        except Exception as exc:  # noqa: BLE001 - surface to the client as an event
            main_loop.call_soon_threadsafe(
                queue.put_nowait,
                {"type": "run_error", "loop": loop_name, "error": str(exc)},
            )
        finally:
            main_loop.call_soon_threadsafe(queue.put_nowait, None)

    async def event_generator() -> Any:
        threading.Thread(target=worker, name=f"live-{loop_name}", daemon=True).start()
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield {"event": "loop_event", "data": json.dumps(event)}
                if delay:
                    await asyncio.sleep(delay)
            yield {"event": "loop_done", "data": json.dumps({"loop": loop_name})}
        finally:
            shutil.rmtree(run_dir.parent, ignore_errors=True)

    return EventSourceResponse(event_generator())


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "loops": list(LIVE_LOOPS)})


def create_app() -> Starlette:
    return Starlette(
        routes=[
            Route("/api/health", health),
            Route("/api/stream", stream),
        ],
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["GET"],
                allow_headers=["*"],
            )
        ],
    )


app = create_app()
