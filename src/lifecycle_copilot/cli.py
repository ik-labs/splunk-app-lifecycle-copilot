from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .appinspect.loop import AppInspectLoop
from .onboarding.loop import OnboardingLoop
from .spl_lint.loop import SplLintLoop


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "appinspect":
        return run_appinspect(args)
    if args.command == "onboard":
        return run_onboard(args)
    if args.command == "lint":
        return run_lint(args)
    if args.command == "serve":
        return run_serve(args)

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

    onboard = subcommands.add_parser(
        "onboard",
        help="Validate raw log extraction candidates against Splunk through MCP.",
    )
    onboard.add_argument("log_file", type=Path)
    onboard.add_argument("--out", type=Path, default=None)
    onboard.add_argument("--max-iters", type=int, default=3)

    lint = subcommands.add_parser(
        "lint",
        help="Heal a costly SPL search until it is free of cost anti-patterns.",
    )
    lint.add_argument("spl_file", type=Path)
    lint.add_argument("--out", type=Path, default=None)
    lint.add_argument("--max-iters", type=int, default=5)

    serve = subcommands.add_parser(
        "serve",
        help="Stream live self-heal events to the dashboard over SSE.",
    )
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    return parser


def run_appinspect(args: argparse.Namespace) -> int:
    console = Console()
    run_dir = args.out or default_run_dir("appinspect")

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

    print_next_steps(
        console,
        result.run_dir,
        status=result.status,
        extra=[("AppInspect reports", "appinspect/")],
    )

    return 0 if result.status == "clean" else 2


def run_onboard(args: argparse.Namespace) -> int:
    console = Console()
    run_dir = args.out or default_run_dir("onboarding")

    try:
        result = OnboardingLoop(
            log_file=args.log_file,
            run_dir=run_dir,
            max_iters=args.max_iters,
        ).run()
    except FileExistsError as exc:
        console.print(f"[red]Run failed:[/red] {exc}")
        return 2
    except Exception as exc:
        console.print(f"[red]Run failed:[/red] {exc}")
        return 1

    table = Table(title="Onboarding MCP Self-Heal Summary")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Status", result.status)
    table.add_row("Iterations", str(result.iterations))
    table.add_row("Ingested events", str(result.ingested_count))
    table.add_row("Initial failures", str(result.initial_summary.get("failure", 0)))
    table.add_row("Final failures", str(result.final_summary.get("failure", 0)))
    table.add_row("Splunk source", result.splunk_source)
    table.add_row("Run artifacts", str(result.run_dir))
    console.print(table)

    print_next_steps(
        console,
        result.run_dir,
        status=result.status,
        extra=[("Candidates & validation", "onboarding/")],
    )

    return 0 if result.status == "clean" else 2


def run_lint(args: argparse.Namespace) -> int:
    console = Console()
    run_dir = args.out or default_run_dir("spl-lint")

    try:
        result = SplLintLoop(
            source_query=args.spl_file,
            run_dir=run_dir,
            max_iters=args.max_iters,
        ).run()
    except FileExistsError as exc:
        console.print(f"[red]Run failed:[/red] {exc}")
        return 2
    except Exception as exc:
        console.print(f"[red]Run failed:[/red] {exc}")
        return 1

    table = Table(title="Cost-Aware SPL Lint Self-Heal Summary")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Status", result.status)
    table.add_row("Iterations", str(result.iterations))
    table.add_row("Initial findings", str(result.initial_summary.get("failure", 0)))
    table.add_row("Final findings", str(result.final_summary.get("failure", 0)))
    table.add_row("Work query", str(result.work_query))
    table.add_row("Run artifacts", str(result.run_dir))
    console.print(table)

    print_next_steps(
        console,
        result.run_dir,
        status=result.status,
        extra=[("SPL lint reports", "spl/")],
    )

    return 0 if result.status == "clean" else 2


def run_serve(args: argparse.Namespace) -> int:
    import uvicorn

    console = Console()
    console.print(
        Panel(
            "\n".join(
                [
                    f"  Live SSE endpoint:  [cyan]http://{args.host}:{args.port}/api/stream?loop=appinspect[/cyan]",
                    "  Also available:     [cyan]?loop=spl_lint[/cyan]  (both static, no Splunk needed)",
                    "",
                    "  In the dashboard, click [bold]Go Live[/bold] on the AppInspect or SPL Lint stage.",
                ]
            ),
            title="Live self-heal stream",
            border_style="green",
            expand=False,
        )
    )
    uvicorn.run("lifecycle_copilot.server:app", host=args.host, port=args.port, log_level="warning")
    return 0


def print_next_steps(
    console: Console,
    run_dir: Path,
    *,
    status: str,
    extra: list[tuple[str, str]],
) -> None:
    """Print an obvious 'what to look at next' panel after a run."""
    clean = status == "clean"
    headline = (
        "[green]Healed to clean[/green] — every diagnosis, patch, and validation is recorded."
        if clean
        else f"[yellow]Run ended '{status}'[/yellow] — open the provenance ledger for the remaining failure."
    )
    pointers: list[tuple[str, str]] = [
        ("Provenance ledger (audit trail)", "provenance.jsonl"),
        ("Run summary", "summary.json"),
        *extra,
        ("Dashboard replay events", "events.json"),
    ]
    lines = [headline, ""]
    width = max(len(label) for label, _ in pointers)
    for label, rel in pointers:
        lines.append(f"  {label.ljust(width)}  [cyan]{run_dir / rel}[/cyan]")
    lines.append("")
    lines.append(
        "  Replay it:  [bold]cd ui/dashboard && bun run dev[/bold], then "
        f"\"Load events\" -> [cyan]{run_dir / 'events.json'}[/cyan]"
    )
    console.print(
        Panel(
            "\n".join(lines),
            title="What to look at next",
            border_style="green" if clean else "yellow",
            expand=False,
        )
    )


def default_run_dir(prefix: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path("runs") / f"{prefix}-{timestamp}"
