from pathlib import Path

from lifecycle_copilot.onboarding.candidates import candidate_00, candidate_01
from lifecycle_copilot.onboarding.validator import validate_candidate_rows


RAW_WITH_MOBILE = (
    "2026-06-02T10:03:52+05:30 txn_id=UPI1 method=UPI_QR "
    "vpa=merchant@oksbi amt=1971.36 status=SUCCESS rrn=366084226887 "
    "payer_mobile=9736806745 payer_vpa=customer1761@ibl gstin=29HYENF5085F1ZM"
)
RAW_WITHOUT_MOBILE = (
    "1780381199979 txn_id=UPI2 method=UPI_MANDATE vpa=merchant@ybl "
    "amt=4823.86 status=TIMEOUT rrn=801775263434 payer_vpa=customer6959@okicici "
    "gstin=07BWTVM6070O1ZM"
)


def robust_rows() -> list[dict[str, str]]:
    return [
        {
            "_raw": RAW_WITH_MOBILE,
            "event_time": "2026-06-02T10:03:52+05:30",
            "txn_id": "UPI1",
            "method": "UPI_QR",
            "vpa": "merchant@oksbi",
            "dest": "merchant@oksbi",
            "amt": "1971.36",
            "amount": "1971.36",
            "status": "SUCCESS",
            "action": "success",
            "rrn": "366084226887",
            "payer_mobile": "9736806745",
            "payer_vpa": "customer1761@ibl",
            "src_user": "customer1761@ibl",
            "gstin": "29HYENF5085F1ZM",
            "vendor_id": "29HYENF5085F1ZM",
            "transaction_id": "UPI1",
            "pii_payer_vpa": "true",
            "pii_payer_mobile": "true",
        },
        {
            "_raw": RAW_WITHOUT_MOBILE,
            "event_time": "1780381199979",
            "txn_id": "UPI2",
            "method": "UPI_MANDATE",
            "vpa": "merchant@ybl",
            "dest": "merchant@ybl",
            "amt": "4823.86",
            "amount": "4823.86",
            "status": "TIMEOUT",
            "action": "timeout",
            "rrn": "801775263434",
            "payer_vpa": "customer6959@okicici",
            "src_user": "customer6959@okicici",
            "gstin": "07BWTVM6070O1ZM",
            "vendor_id": "07BWTVM6070O1ZM",
            "transaction_id": "UPI2",
            "pii_payer_vpa": "true",
        },
    ]


def test_validator_detects_missing_fields_from_fake_mcp_rows(tmp_path: Path) -> None:
    candidate = candidate_00(index="main", sourcetype="upi_gateway_raw", source="source")
    rows = [{"_raw": RAW_WITH_MOBILE, "txn_id": "UPI1"}]

    result = validate_candidate_rows(
        candidate=candidate,
        rows=rows,
        report_path=tmp_path / "validation-00.json",
    )

    assert result.summary["failure"] >= 1
    assert "field_coverage_gap" in {failure.check for failure in result.failures}
    assert "cim_mapping_gap" in {failure.check for failure in result.failures}
    assert "pii_flag_gap" in {failure.check for failure in result.failures}


def test_validator_passes_robust_candidate_fake_rows(tmp_path: Path) -> None:
    candidate = candidate_01(index="main", sourcetype="upi_gateway_raw", source="source")

    result = validate_candidate_rows(
        candidate=candidate,
        rows=robust_rows(),
        report_path=tmp_path / "validation-01.json",
    )

    assert result.summary["failure"] == 0
    assert result.failures == ()
    assert len(result.extracted_mappings) == 6
    assert set(result.pii_fields) == {"payer_vpa", "payer_mobile"}
    assert result.report_path.exists()
