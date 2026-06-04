from lifecycle_copilot.onboarding.candidates import candidate_00, candidate_01


def test_robust_candidate_contains_required_extractions_aliases_and_pii_flags() -> None:
    candidate = candidate_01(
        index="main",
        sourcetype="upi_gateway_raw",
        source="copilot:onboarding:test",
    )

    assert "rex field=_raw" in candidate.spl
    assert "txn_id" in candidate.spl
    assert "payer_mobile" in candidate.spl
    assert "event_time" in candidate.spl
    assert "amount=tonumber(amt)" in candidate.spl
    assert "action=case" in candidate.spl
    assert "dest=vpa" in candidate.spl
    assert "src_user=payer_vpa" in candidate.spl
    assert "transaction_id=txn_id" in candidate.spl
    assert "vendor_id=gstin" in candidate.spl
    assert "pii_payer_vpa" in candidate.spl
    assert "pii_payer_mobile" in candidate.spl


def test_naive_candidate_is_positional_and_missing_robust_pii_flagging() -> None:
    candidate = candidate_00(
        index="main",
        sourcetype="upi_gateway_raw",
        source="copilot:onboarding:test",
    )

    assert r"txn_id=(?<txn_id>\S+)\s+method=" in candidate.spl
    assert "pii_payer_mobile=if" not in candidate.spl
