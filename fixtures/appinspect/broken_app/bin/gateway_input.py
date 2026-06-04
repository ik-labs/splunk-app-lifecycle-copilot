#!/usr/bin/env python3
"""Placeholder modular input that pulls UPI gateway events.

The AppInspect failure fixture is seeded through configuration files rather
than hardcoded runtime credentials so the local CLI produces deterministic
failure results.
"""
import sys

GATEWAY_NAME = "upi_gateway_demo"


def fetch_events():
    print(f"connecting to {GATEWAY_NAME}...", file=sys.stderr)
    return []


if __name__ == "__main__":
    fetch_events()
