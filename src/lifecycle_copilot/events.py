from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass
class EventRecorder:
    run_dir: Path
    events: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.run_dir = Path(self.run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.run_dir / "events.jsonl"
        self.json_path = self.run_dir / "events.json"
        self.jsonl_path.write_text("", encoding="utf-8")

    def emit(self, event_type: str, **fields: Any) -> dict[str, Any]:
        event = {"type": event_type, "ts": fields.pop("ts", utc_now())}
        event.update(fields)
        self.events.append(event)
        with self.jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=True) + "\n")
        return event

    def write_snapshot(self) -> Path:
        self.json_path.write_text(
            json.dumps(self.events, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return self.json_path
