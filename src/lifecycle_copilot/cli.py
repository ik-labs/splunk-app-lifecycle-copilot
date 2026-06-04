from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .appinspect.loop import AppInspectLoop


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "appinspect":
        return run_appinspect(args)

    parser.error("No command selected.")
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="copilot")
    subcommands = parser.add_subparsers(dest="command", required=True)

    appinspect = subcommands.add_parser(
        "appinspect",
        help="Heal a Splunk app until AppInspect reports zero failures.",
    )
    appinspect.add_argument("app_dir", type=Path)
    appinspect.add_argument("--out", type=Path, default=None)
    appinspect.add_argument("--max-iters", type=int, default=5)
    return parser


def run_appinspect(args: argparse.Namespace) -> int:
    console = Console()
    run_dir = args.out or default_run_dir()

    try:
        result = AppInspectLoop(
            source_app=args.app_dir,
            run_dir=run_dir,
            max_iters=args.max_iters,
        ).run()
    except FileExistsError as exc:
        console.print(f"[red]Run failed:[/red] {exc}")
        return 2
    except Exception as exc:
        console.print(f"[red]Run failed:[/red] {exc}")
        return 1

    table = Table(title="AppInspect Self-Heal Summary")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Status", result.status)
    table.add_row("Iterations", str(result.iterations))
    table.add_row("Initial failures", str(result.initial_summary.get("failure", 0)))
    table.add_row("Final failures", str(result.final_summary.get("failure", 0)))
    table.add_row("Work app", str(result.work_app))
    table.add_row("Run artifacts", str(result.run_dir))
    console.print(table)

    return 0 if result.status == "clean" else 2


def default_run_dir() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path("runs") / f"appinspect-{timestamp}"
