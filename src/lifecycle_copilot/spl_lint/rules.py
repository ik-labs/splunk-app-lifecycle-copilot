from __future__ import annotations

import re
from dataclasses import dataclass

from lifecycle_copilot.diagnosis import Diagnosis


@dataclass(frozen=True)
class SplFinding:
    """A single cost/anti-pattern finding in an SPL search."""

    failure_id: str
    check: str
    file: str | None
    line: int | None
    message: str


# Regexes are deliberately conservative so detection and the matching
# deterministic rewrite always agree.
_WILDCARD_INDEX = re.compile(r"\bindex\s*=\s*\*")
_ANY_INDEX = re.compile(r"\bindex\s*=")
_TIME_BOUND = re.compile(r"\b(?:earliest|latest|_index_earliest|_index_latest)\s*=")
# A `| sort` whose first argument is not an integer result limit.
_UNBOUNDED_SORT = re.compile(r"\|\s*sort\s+(?!\d)")


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def lint_spl(text: str, *, file: str | None = None) -> list[SplFinding]:
    """Return cost findings for a single SPL search, in priority order."""
    findings: list[SplFinding] = []

    def add(check: str, line: int, message: str) -> None:
        findings.append(
            SplFinding(
                failure_id=f"spl_lint:{check}",
                check=check,
                file=file,
                line=line,
                message=message,
            )
        )

    wildcard_index = _WILDCARD_INDEX.search(text)
    if wildcard_index:
        add(
            "spl_wildcard_index",
            _line_of(text, wildcard_index.start()),
            "Search runs against index=*, scanning every index on the instance.",
        )
    elif not _ANY_INDEX.search(text):
        add(
            "spl_missing_index",
            1,
            "Search does not specify an index, so Splunk scans the default index set.",
        )

    if not _TIME_BOUND.search(text):
        add(
            "spl_all_time",
            1,
            "Search has no earliest/latest bound, so it can scan the full retention window.",
        )

    unbounded_sort = _UNBOUNDED_SORT.search(text)
    if unbounded_sort:
        add(
            "spl_unbounded_sort",
            _line_of(text, unbounded_sort.start()),
            "| sort has no result limit, so the entire result set is buffered and ordered.",
        )

    return findings


SPL_DIAGNOSES: dict[str, Diagnosis] = {
    "spl_wildcard_index": Diagnosis(
        text=(
            "The search runs against index=*, which forces Splunk to scan every index "
            "on the instance instead of only the relevant data."
        ),
        rationale="Pin the search to a specific index (index=main) so only relevant buckets are read.",
    ),
    "spl_missing_index": Diagnosis(
        text=(
            "The search specifies no index, so Splunk falls back to the role's default "
            "index set and reads more buckets than necessary."
        ),
        rationale="Add an explicit index=main filter to bound the search to one index.",
    ),
    "spl_all_time": Diagnosis(
        text=(
            "The search declares no earliest/latest time bound, so it can scan the full "
            "retention window and do far more work than the question requires."
        ),
        rationale="Add an explicit earliest=-24h window so the search reads a bounded time range.",
    ),
    "spl_unbounded_sort": Diagnosis(
        text=(
            "The | sort command has no result limit, so Splunk must buffer and order the "
            "entire result set, which is memory- and time-intensive on large searches."
        ),
        rationale="Cap the sort with an explicit limit (| sort 1000 ...) to bound memory and time.",
    ),
}


def diagnose_spl(finding: object) -> Diagnosis:
    check = getattr(finding, "check", "")
    return SPL_DIAGNOSES.get(
        check,
        Diagnosis(
            text=f"The SPL linter reported {check or 'an unsupported rule'} as a finding.",
            rationale=(
                "No free-form rewrite is attempted; only deterministic patchers from the "
                "registry may change the search."
            ),
        ),
    )
