from __future__ import annotations

from lifecycle_copilot.self_heal import PatchResult

from .rules import (
    _UNBOUNDED_SORT,
    _WILDCARD_INDEX,
    SplFinding,
)


class SplLintPatchError(RuntimeError):
    pass


# Order in which findings are healed; index first, then time, then sort.
PATCH_PRIORITY = (
    "spl_wildcard_index",
    "spl_missing_index",
    "spl_all_time",
    "spl_unbounded_sort",
)


def select_spl_finding(
    findings: list[SplFinding] | tuple[SplFinding, ...],
) -> SplFinding:
    for check in PATCH_PRIORITY:
        for finding in findings:
            if finding.check == check:
                return finding
    checks = ", ".join(sorted({finding.check for finding in findings}))
    raise SplLintPatchError(f"No deterministic SPL patcher for findings: {checks}")


def apply_spl_patch(text: str, finding: SplFinding) -> tuple[str, PatchResult]:
    patcher = PATCHERS.get(finding.check)
    if patcher is None:
        raise SplLintPatchError(f"No deterministic SPL patcher for {finding.check}")
    new_text, result = patcher(text)
    if finding.file:
        result = PatchResult(
            patch_id=result.patch_id,
            summary=result.summary,
            changed_paths=(finding.file,),
        )
    return new_text, result


def _prepend_term(text: str, term: str) -> str:
    """Insert a leading search term after any leading whitespace."""
    stripped = text.lstrip()
    leading = text[: len(text) - len(stripped)]
    return f"{leading}{term} {stripped}"


def _fix_wildcard_index(text: str) -> tuple[str, PatchResult]:
    new_text = _WILDCARD_INDEX.sub("index=main", text, count=1)
    return new_text, PatchResult(
        patch_id="spl_lint.pin_index",
        summary="Replaced index=* with index=main to bound the search to one index.",
        changed_paths=("query.spl",),
    )


def _fix_missing_index(text: str) -> tuple[str, PatchResult]:
    new_text = _prepend_term(text, "index=main")
    return new_text, PatchResult(
        patch_id="spl_lint.add_index",
        summary="Added an explicit index=main filter to the base search.",
        changed_paths=("query.spl",),
    )


def _fix_all_time(text: str) -> tuple[str, PatchResult]:
    new_text = _prepend_term(text, "earliest=-24h")
    return new_text, PatchResult(
        patch_id="spl_lint.bound_time",
        summary="Added an explicit earliest=-24h window to bound the time range.",
        changed_paths=("query.spl",),
    )


def _fix_unbounded_sort(text: str) -> tuple[str, PatchResult]:
    new_text = _UNBOUNDED_SORT.sub(lambda match: f"{match.group(0)}1000 ", text, count=1)
    return new_text, PatchResult(
        patch_id="spl_lint.bound_sort",
        summary="Capped | sort with an explicit 1000-row limit.",
        changed_paths=("query.spl",),
    )


PATCHERS = {
    "spl_wildcard_index": _fix_wildcard_index,
    "spl_missing_index": _fix_missing_index,
    "spl_all_time": _fix_all_time,
    "spl_unbounded_sort": _fix_unbounded_sort,
}
