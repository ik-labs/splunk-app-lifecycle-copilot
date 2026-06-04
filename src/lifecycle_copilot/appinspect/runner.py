from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .parser import AppInspectFailure, parse_appinspect_report


class AppInspectExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class AppInspectRun:
    iteration: int
    report_path: Path
    summary: dict[str, int]
    failures: tuple[AppInspectFailure, ...]
    returncode: int
    stdout: str
    stderr: str


def default_appinspect_binary() -> str:
    configured = os.getenv("SPLUNK_APPINSPECT_BIN") or os.getenv("APPINSPECT_BIN")
    if configured:
        return configured

    venv_candidate = Path(sys.executable).with_name("splunk-appinspect")
    if venv_candidate.exists():
        return str(venv_candidate)

    return "splunk-appinspect"


class AppInspectRunner:
    def __init__(self, binary: str | None = None) -> None:
        self.binary = binary or default_appinspect_binary()

    def inspect(self, app_dir: Path, output_path: Path, *, iteration: int) -> AppInspectRun:
        app_dir = Path(app_dir)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        command = [
            self.binary,
            "inspect",
            str(app_dir),
            "--mode",
            "test",
            "--data-format",
            "json",
            "--output-file",
            str(output_path),
        ]
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )

        if not output_path.exists():
            raise AppInspectExecutionError(
                "AppInspect did not produce a JSON report.\n"
                f"Command: {' '.join(command)}\n"
                f"Return code: {completed.returncode}\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )

        try:
            report = json.loads(output_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AppInspectExecutionError(f"AppInspect wrote invalid JSON: {output_path}") from exc

        summary, failures = parse_appinspect_report(report)
        return AppInspectRun(
            iteration=iteration,
            report_path=output_path,
            summary={key: int(value) for key, value in summary.items()},
            failures=tuple(failures),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
