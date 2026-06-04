# Onboarding fixture — expected outcome (ground truth)

This file defines what "CIM-clean" means for `sample_upi.log`, so the
onboarding loop has a target to iterate toward and the demo has a clear
before/after. The loop should converge on this; it is NOT given this as input.

## Source format challenges (why a naive extraction fails)

1. **Two timestamp formats interleaved** — ISO-8601 with `+05:30` offset AND
   epoch-millis. A single `TIME_FORMAT` won't cover both; the loop must detect
   and handle both (or normalize).
2. **Variable field order / presence** — `rrn` is missing on ~15% of lines;
   `payer_mobile` appears on ~20%. A positional regex breaks; key=value
   extraction is needed.
3. **Non-CIM field names** — fields use payment-domain names that must be
   aliased to CIM equivalents (see mapping below).
4. **Malformed lines** (~5%) — partial records and marker lines the extraction
   must survive without erroring.

## Target field extraction (key=value)

| Raw field      | Extract? | Notes                                  |
|----------------|----------|----------------------------------------|
| `txn_id`       | yes      | transaction identifier                 |
| `method`       | yes      | UPI flow type                          |
| `vpa`          | yes      | merchant VPA                           |
| `amt`          | yes      | transaction amount                     |
| `status`       | yes      | transaction outcome                    |
| `rrn`          | yes      | may be absent — must not fail          |
| `payer_vpa`    | yes      | **PII — must be flagged**              |
| `payer_mobile` | yes      | **PII — must be flagged** (when present)|
| `gstin`        | yes      | GST number; first 2 chars = state code |

## Target CIM mapping (Transactions / Authentication-adjacent)

The loop should propose field aliases mapping the raw names to CIM:

| Raw name     | CIM field    | CIM data model        |
|--------------|--------------|-----------------------|
| `amt`        | `amount`     | (Transactions-style)  |
| `status`     | `action`     | SUCCESS->success etc. |
| `vpa`        | `dest`       | payment destination   |
| `payer_vpa`  | `src_user`   | payment source (PII)  |
| `txn_id`     | `transaction_id` |                   |
| `gstin`      | `vendor_id`  |                       |

(Exact CIM model choice is a judgment call the agent makes and explains in the
provenance ledger — the point is that it reasons about it, not that it picks a
canonical answer.)

## PII detection (must-flag)

The loop MUST surface these as PII before "passing":
- `payer_vpa` — personal payment handle
- `payer_mobile` — personal phone number

A run that produces clean extraction but does NOT flag these is a FAIL for the
onboarding loop's PII gate.

## Success criteria for the loop

1. All 9 fields extract on well-formed lines.
2. Both timestamp formats handled.
3. Malformed lines do not break the extraction.
4. CIM aliases proposed for the mappable fields.
5. PII fields flagged.
6. Every iteration (what failed, what was patched, why) written to the
   provenance ledger.
