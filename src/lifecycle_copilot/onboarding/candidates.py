from __future__ import annotations

from .models import Candidate


RAW_FIELDS = (
    "txn_id",
    "method",
    "vpa",
    "amt",
    "status",
    "rrn",
    "payer_vpa",
    "payer_mobile",
    "gstin",
)

CIM_MAPPINGS = (
    ("amt", "amount"),
    ("status", "action"),
    ("vpa", "dest"),
    ("payer_vpa", "src_user"),
    ("txn_id", "transaction_id"),
    ("gstin", "vendor_id"),
)

PII_FIELDS = ("payer_vpa", "payer_mobile")

TABLE_FIELDS = (
    "_raw",
    "event_time",
    "txn_id",
    "method",
    "vpa",
    "dest",
    "amt",
    "amount",
    "status",
    "action",
    "rrn",
    "payer_vpa",
    "src_user",
    "payer_mobile",
    "gstin",
    "vendor_id",
    "transaction_id",
    "pii_payer_vpa",
    "pii_payer_mobile",
)


def build_base_search(index: str, sourcetype: str, source: str) -> str:
    return (
        f'search index={_quote_spl_token(index)} '
        f'sourcetype={_quote_spl_token(sourcetype)} '
        f'source="{_quote_spl_string(source)}" earliest=-15m latest=now'
    )


def get_candidate(
    candidate_id: str,
    *,
    index: str,
    sourcetype: str,
    source: str,
) -> Candidate:
    if candidate_id == "candidate-00":
        return candidate_00(index=index, sourcetype=sourcetype, source=source)
    if candidate_id == "candidate-01":
        return candidate_01(index=index, sourcetype=sourcetype, source=source)
    raise KeyError(f"Unknown onboarding SPL candidate: {candidate_id}")


def candidate_00(*, index: str, sourcetype: str, source: str) -> Candidate:
    base_search = build_base_search(index, sourcetype, source)
    spl = "\n".join(
        (
            base_search,
            r'| rex field=_raw "^(?<event_time>\d{4}-\d{2}-\d{2}T\S+)"',
            (
                r'| rex field=_raw "txn_id=(?<txn_id>\S+)\s+method=(?<method>\S+)'
                r'\s+vpa=(?<vpa>\S+)\s+amt=(?<amt>\S+)\s+status=(?<status>\S+)'
                r'\s+rrn=(?<rrn>\S+)\s+payer_vpa=(?<payer_vpa>\S+)'
                r'\s+gstin=(?<gstin>\S+)"'
            ),
            (
                "| eval amount=tonumber(amt), dest=vpa, src_user=payer_vpa, "
                "transaction_id=txn_id, vendor_id=gstin"
            ),
            f"| table {' '.join(TABLE_FIELDS)}",
        )
    )
    return Candidate(
        candidate_id="candidate-00",
        description="Naive positional extraction that breaks on optional fields and order drift.",
        spl=spl,
    )


def candidate_01(*, index: str, sourcetype: str, source: str) -> Candidate:
    base_search = build_base_search(index, sourcetype, source)
    spl = "\n".join(
        (
            base_search,
            r'| rex field=_raw "^(?<event_time>(?:\d{13}|\d{4}-\d{2}-\d{2}T\S+))"',
            r'| rex field=_raw "(?:^|\s)txn_id=(?<txn_id>\S+)"',
            r'| rex field=_raw "(?:^|\s)method=(?<method>\S+)"',
            r'| rex field=_raw "(?:^|\s)vpa=(?<vpa>\S+)"',
            r'| rex field=_raw "(?:^|\s)amt=(?<amt>\S+)"',
            r'| rex field=_raw "(?:^|\s)status=(?<status>\S+)"',
            r'| rex field=_raw "(?:^|\s)rrn=(?<rrn>\S+)"',
            r'| rex field=_raw "(?:^|\s)payer_vpa=(?<payer_vpa>\S+)"',
            r'| rex field=_raw "(?:^|\s)payer_mobile=(?<payer_mobile>\S+)"',
            r'| rex field=_raw "(?:^|\s)gstin=(?<gstin>\S+)"',
            "| eval amount=tonumber(amt)",
            (
                '| eval action=case(status="SUCCESS","success",status="FAILED","failure",'
                'status="REVERSED","failure",status="PENDING","pending",'
                'status="TIMEOUT","timeout",isnotnull(status),lower(status))'
            ),
            "| eval dest=vpa, src_user=payer_vpa, transaction_id=txn_id, vendor_id=gstin",
            '| eval pii_payer_vpa=if(isnotnull(payer_vpa),"true",null())',
            '| eval pii_payer_mobile=if(isnotnull(payer_mobile),"true",null())',
            f"| table {' '.join(TABLE_FIELDS)}",
        )
    )
    return Candidate(
        candidate_id="candidate-01",
        description="Robust key/value extraction with CIM aliases and PII flags.",
        spl=spl,
    )


def _quote_spl_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', r"\"")


def _quote_spl_token(value: str) -> str:
    if not value.replace("_", "").replace("-", "").isalnum():
        return f'"{_quote_spl_string(value)}"'
    return value
