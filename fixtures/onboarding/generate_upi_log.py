#!/usr/bin/env python3
"""
Generates a synthetic UPI / GST payment-gateway log for the onboarding loop.

Design goals (this is the point — the data must be HARD to onboard cleanly):
  - Mixed key=value and positional fields, so a naive regex misses several.
  - Two timestamp formats interleaved (ISO+offset and epoch millis), so
    TIME_FORMAT/timestamp extraction needs iteration.
  - Fields that SHOULD map to CIM but use non-CIM names (vpa, payer_vpa,
    amt, status) -> forces the CIM-mapping step to do real work.
  - At least one clear PII field (payer_vpa, sometimes a phone) -> the loop
    must FLAG it, not silently pass.
  - Occasional malformed / partial lines -> the loop must be robust.

Usage:
    python generate_upi_log.py --lines 150 --out sample_upi.log
"""
import argparse
import random
import time
from datetime import datetime, timedelta, timezone

BANKS = ["okhdfcbank", "okaxis", "oksbi", "okicici", "ybl", "paytm", "ibl"]
MERCHANTS = ["chai_point", "more_retail", "reliance_fresh", "local_kirana",
             "medplus", "swiggy", "bigbasket"]
STATUSES = ["SUCCESS", "FAILED", "PENDING", "TIMEOUT", "REVERSED"]
GST_STATES = ["24", "27", "29", "07", "33", "19"]  # GJ, MH, KA, DL, TN, WB
METHODS = ["UPI_COLLECT", "UPI_INTENT", "UPI_QR", "UPI_MANDATE"]
IST = timezone(timedelta(hours=5, minutes=30))


def rand_gstin(state):
    pan = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=5))
    digits = "".join(random.choices("0123456789", k=4))
    letter = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    return f"{state}{pan}{digits}{letter}1ZM"


def rand_phone():
    return "9" + "".join(random.choices("0123456789", k=9))


def make_line(ts_mode):
    txn_id = "UPI" + datetime.now().strftime("%Y%m%d") + "".join(
        random.choices("0123456789", k=11))
    bank = random.choice(BANKS)
    merchant = random.choice(MERCHANTS)
    amt = round(random.uniform(10, 9999), 2)
    status = random.choices(STATUSES, weights=[60, 15, 10, 8, 7])[0]
    rrn = "".join(random.choices("0123456789", k=12))
    state = random.choice(GST_STATES)
    gstin = rand_gstin(state)
    method = random.choice(METHODS)
    payer = "customer" + "".join(random.choices("0123456789", k=4)) + "@" + \
        random.choice(BANKS)

    # Two timestamp formats, interleaved on purpose.
    now = datetime.now(IST) - timedelta(seconds=random.randint(0, 86400))
    if ts_mode == "iso":
        ts = now.isoformat(timespec="seconds")
    else:
        ts = str(int(now.timestamp() * 1000))  # epoch millis

    # Field ORDER and presence vary slightly to stress the extraction.
    parts = [
        ts,
        f"txn_id={txn_id}",
        f"method={method}",
        f"vpa=merchant_{merchant}@{bank}",
        f"amt={amt}",
        f"status={status}",
        f"rrn={rrn}",
        f"payer_vpa={payer}",
        f"gstin={gstin}",
    ]
    # ~20% of lines also carry a phone (extra PII to flag), and ~15% drop rrn.
    if random.random() < 0.2:
        parts.insert(7, f"payer_mobile={rand_phone()}")
    if random.random() < 0.15:
        parts = [p for p in parts if not p.startswith("rrn=")]
    return " ".join(parts)


def make_malformed():
    # Partial/truncated line the loop must survive.
    return random.choice([
        "2026-06-01T10:00:00+05:30 txn_id=UPI20260601 status=",
        str(int(time.time() * 1000)) + " amt=500.00 PARTIAL_RECORD",
        "### gateway restart marker ###",
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lines", type=int, default=150)
    ap.add_argument("--out", default="sample_upi.log")
    ap.add_argument("--malformed-rate", type=float, default=0.05)
    args = ap.parse_args()

    rows = []
    for _ in range(args.lines):
        if random.random() < args.malformed_rate:
            rows.append(make_malformed())
        else:
            rows.append(make_line(random.choice(["iso", "epoch"])))

    with open(args.out, "w") as f:
        f.write("\n".join(rows) + "\n")
    print(f"Wrote {len(rows)} lines to {args.out}")


if __name__ == "__main__":
    main()
