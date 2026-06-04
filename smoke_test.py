#!/usr/bin/env python3
"""
Day-1 smoke test. Run this BEFORE building any agent code to confirm the
plumbing works: Splunk login, HEC ingest, search round-trip, and that
splunk-appinspect is installed. If all four pass, both loops are unblocked.

Usage:
    pip install splunk-sdk requests python-dotenv splunk-appinspect
    docker compose up -d        # wait until 'healthy' (~1-2 min)
    python smoke_test.py
"""
import os
import sys
import time
import subprocess

import requests
from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv("SPLUNK_HOST", "localhost")
MGMT_PORT = int(os.getenv("SPLUNK_MGMT_PORT", "8089"))
HEC_PORT = int(os.getenv("SPLUNK_HEC_PORT", "8088"))
USERNAME = os.getenv("SPLUNK_USERNAME", "admin")
PASSWORD = os.getenv("SPLUNK_PASSWORD")
HEC_TOKEN = os.getenv("SPLUNK_HEC_TOKEN")


def ok(msg):
    print(f"  [PASS] {msg}")


def fail(msg):
    print(f"  [FAIL] {msg}")
    sys.exit(1)


def test_sdk_login():
    print("1. Splunk SDK login (port 8089)...")
    try:
        import splunklib.client as client
        service = client.connect(
            host=HOST, port=MGMT_PORT, username=USERNAME, password=PASSWORD,
        )
        _ = service.apps  # force a call
        ok(f"connected, {len(list(service.apps))} apps visible")
        return service
    except Exception as e:
        fail(f"SDK login failed: {e}")


def test_hec_ingest():
    print("2. HEC ingest (port 8088)...")
    url = f"https://{HOST}:{HEC_PORT}/services/collector/event"
    headers = {"Authorization": f"Splunk {HEC_TOKEN}"}
    payload = {"event": "smoke_test_event src_ip=10.0.0.1 action=login",
               "sourcetype": "smoke_test"}
    try:
        r = requests.post(url, json=payload, headers=headers, verify=False, timeout=10)
        if r.status_code == 200:
            ok("event accepted by HEC")
        else:
            fail(f"HEC returned {r.status_code}: {r.text}")
    except Exception as e:
        fail(f"HEC ingest failed: {e}")


def test_search(service):
    print("3. Search round-trip (gives indexing a few seconds)...")
    time.sleep(8)  # let the event index
    try:
        import splunklib.results as results
        job = service.jobs.oneshot('search sourcetype=smoke_test | head 1',
                                   output_mode='json')
        rows = list(results.JSONResultsReader(job))
        if rows:
            ok("search returned the ingested event")
        else:
            print("  [WARN] no rows yet — indexing can lag; re-run if needed")
    except Exception as e:
        fail(f"search failed: {e}")


def test_appinspect():
    print("4. splunk-appinspect CLI installed...")
    try:
        r = subprocess.run(["splunk-appinspect", "list", "version"],
                           capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            ok(f"appinspect available: {r.stdout.strip().splitlines()[0]}")
        else:
            fail(f"appinspect error: {r.stderr}")
    except FileNotFoundError:
        fail("splunk-appinspect not found — run: pip install splunk-appinspect")
    except Exception as e:
        fail(f"appinspect check failed: {e}")


if __name__ == "__main__":
    requests.packages.urllib3.disable_warnings()  # local self-signed cert
    print("\n=== Splunk App Lifecycle Copilot — Day-1 smoke test ===\n")
    svc = test_sdk_login()
    test_hec_ingest()
    test_search(svc)
    test_appinspect()
    print("\nAll critical checks passed. Both loops are unblocked.\n")
