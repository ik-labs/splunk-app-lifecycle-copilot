from __future__ import annotations

from lifecycle_copilot.spl_lint.patchers import (
    PATCH_PRIORITY,
    SplLintPatchError,
    apply_spl_patch,
    select_spl_finding,
)
from lifecycle_copilot.spl_lint.rules import diagnose_spl, lint_spl

COSTLY = "index=* sourcetype=upi_gateway_raw status=FAILED | sort -_time | stats count by payer_vpa"
CLEAN = "earliest=-24h index=main status=FAILED | sort 1000 -_time | stats count"


def test_lint_finds_three_cost_findings() -> None:
    findings = lint_spl(COSTLY, file="query.spl")
    checks = [finding.check for finding in findings]
    assert checks == ["spl_wildcard_index", "spl_all_time", "spl_unbounded_sort"]
    assert all(finding.file == "query.spl" for finding in findings)


def test_clean_query_has_no_findings() -> None:
    assert lint_spl(CLEAN) == []


def test_missing_index_fires_only_without_any_index() -> None:
    checks = [finding.check for finding in lint_spl("earliest=-1h sourcetype=foo | head 1")]
    assert "spl_missing_index" in checks
    assert "spl_wildcard_index" not in checks


def test_each_patch_removes_its_finding_and_converges() -> None:
    text = COSTLY
    seen: list[str] = []
    for _ in range(len(PATCH_PRIORITY) + 1):
        findings = lint_spl(text)
        if not findings:
            break
        finding = select_spl_finding(findings)
        seen.append(finding.check)
        text, result = apply_spl_patch(text, finding)
        assert result.changed_paths == ("query.spl",)
    assert lint_spl(text) == []
    assert seen == ["spl_wildcard_index", "spl_all_time", "spl_unbounded_sort"]
    # The healed query is genuinely cheaper.
    assert "index=main" in text
    assert "earliest=-24h" in text
    assert "| sort 1000 -_time" in text


def test_wildcard_index_rewrite_is_targeted() -> None:
    text, _ = apply_spl_patch(
        "index=* foo=bar | stats count",
        select_spl_finding(lint_spl("index=* foo=bar | stats count")),
    )
    assert text.startswith("index=main foo=bar")


def test_select_raises_on_unknown_finding() -> None:
    from lifecycle_copilot.spl_lint.rules import SplFinding

    bogus = SplFinding(
        failure_id="spl_lint:made_up",
        check="made_up",
        file="query.spl",
        line=1,
        message="n/a",
    )
    try:
        select_spl_finding([bogus])
    except SplLintPatchError:
        pass
    else:  # pragma: no cover - guard
        raise AssertionError("expected SplLintPatchError")


def test_diagnose_returns_rule_specific_text() -> None:
    finding = lint_spl(COSTLY)[0]
    diagnosis = diagnose_spl(finding)
    assert "index=*" in diagnosis.text
    assert "index=main" in diagnosis.rationale
