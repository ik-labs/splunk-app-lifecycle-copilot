import { describe, expect, it } from "vitest";

import appinspectEvents from "../../../../demo/appinspect_events.json";
import appinspectProvenanceRaw from "../../../../demo/appinspect_provenance.jsonl?raw";
import onboardingEvents from "../../../../demo/onboarding_events.json";
import onboardingProvenanceRaw from "../../../../demo/onboarding_provenance.jsonl?raw";
import {
  buildAuditTrail,
  deriveReplayState,
  formatLedgerTimestamp,
  parseProvenance,
  summarizeStage
} from "./replay";
import type { LedgerEntryEvent, ReplayEvent } from "../types";

const events: ReplayEvent[] = [
  { type: "run_started", loop: "appinspect", ts: "2026-06-04T00:00:00Z" },
  {
    type: "failure_detected",
    loop: "appinspect",
    ts: "2026-06-04T00:00:01Z",
    failure_id: "f1",
    check: "check_that_local_does_not_exist",
    file: "local/",
    line: null,
    message: "local exists"
  },
  {
    type: "failure_detected",
    loop: "appinspect",
    ts: "2026-06-04T00:00:01Z",
    failure_id: "f2",
    check: "check_user_seed_conf_deny_list",
    file: "default/user-seed.conf",
    line: null,
    message: "seed exists"
  },
  {
    type: "failure_detected",
    loop: "appinspect",
    ts: "2026-06-04T00:00:01Z",
    failure_id: "f3",
    check: "check_if_outputs_conf_exists",
    file: "default/outputs.conf",
    line: null,
    message: "outputs exists"
  },
  {
    type: "unknown_future_event",
    ts: "2026-06-04T00:00:01Z",
    detail: "ignored by reducer"
  },
  {
    type: "diagnosis",
    ts: "2026-06-04T00:00:02Z",
    failure_id: "f1",
    check: "check_that_local_does_not_exist",
    file: "local/",
    line: null,
    message: "local exists",
    text: "local is package-local config"
  },
  {
    type: "patch_applied",
    ts: "2026-06-04T00:00:03Z",
    failure_id: "f1",
    check: "check_that_local_does_not_exist",
    file: "local/",
    line: null,
    message: "local exists",
    summary: "removed local"
  },
  {
    type: "revalidated",
    ts: "2026-06-04T00:00:04Z",
    failure_id: "f1",
    check: "check_that_local_does_not_exist",
    file: "local/",
    line: null,
    message: "local exists",
    result: "pass",
    iteration: 1
  },
  {
    type: "revalidated",
    ts: "2026-06-04T00:00:05Z",
    failure_id: "f2",
    check: "check_user_seed_conf_deny_list",
    file: "default/user-seed.conf",
    line: null,
    message: "seed exists",
    result: "pass",
    iteration: 2
  },
  {
    type: "revalidated",
    ts: "2026-06-04T00:00:06Z",
    failure_id: "f3",
    check: "check_if_outputs_conf_exists",
    file: "default/outputs.conf",
    line: null,
    message: "outputs exists",
    result: "pass",
    iteration: 3
  },
  {
    type: "run_complete",
    ts: "2026-06-04T00:00:07Z",
    loop: "appinspect",
    status: "clean",
    iterations: 3
  }
];

describe("deriveReplayState", () => {
  it("derives the three initial failures", () => {
    const state = deriveReplayState(events, 3);
    expect(state.metrics.initialFailures).toBe(3);
    expect(state.failures.map((failure) => failure.failureId)).toEqual(["f1", "f2", "f3"]);
  });

  it("marks failures healed after pass revalidation events", () => {
    const state = deriveReplayState(events, events.length - 1);
    expect(state.metrics.healed).toBe(3);
    expect(state.metrics.finalFailures).toBe(0);
    expect(state.failures.every((failure) => failure.revalidated === "pass")).toBe(true);
  });

  it("computes the final clean run status", () => {
    const state = deriveReplayState(events, events.length - 1);
    expect(state.runStatus).toBe("clean");
    expect(state.metrics.iterations).toBe(3);
  });

  it("keeps unknown future events visible without crashing", () => {
    const state = deriveReplayState(events, 4);
    expect(state.activeEvent?.type).toBe("unknown_future_event");
    expect(state.visibleEvents).toHaveLength(5);
  });
});

describe("deriveReplayState (onboarding)", () => {
  const onboarding = onboardingEvents as ReplayEvent[];

  it("finds the three initial gaps despite leading mcp_tool_call events", () => {
    const state = deriveReplayState(onboarding, onboarding.length - 1);
    expect(state.metrics.initialFailures).toBe(3);
    expect(state.failures.map((failure) => failure.check)).toEqual([
      "timestamp_coverage_gap",
      "cim_mapping_gap",
      "pii_flag_gap"
    ]);
  });

  it("heals every gap from one candidate swap when the run completes clean", () => {
    const state = deriveReplayState(onboarding, onboarding.length - 1);
    expect(state.runStatus).toBe("clean");
    expect(state.metrics.healed).toBe(3);
    expect(state.metrics.finalFailures).toBe(0);
    expect(state.metrics.iterations).toBe(1);
    expect(state.failures.every((failure) => failure.revalidated === "pass")).toBe(true);
  });

  it("collects CIM mappings, PII flags, and counts MCP tool calls", () => {
    const state = deriveReplayState(onboarding, onboarding.length - 1);
    expect(state.fieldMappings).toHaveLength(6);
    expect(state.fieldMappings).toContainEqual({ raw: "vpa", cim: "dest" });
    expect(state.piiFlags).toEqual(["payer_vpa", "payer_mobile"]);
    expect(state.metrics.mcpCalls).toBeGreaterThan(0);
  });
});

describe("summarizeStage", () => {
  it("summarizes the onboarding loop for the lifecycle overview", () => {
    const summary = summarizeStage(onboardingEvents as ReplayEvent[]);
    expect(summary).toMatchObject({
      runStatus: "clean",
      initialFailures: 3,
      finalFailures: 0,
      healed: 3,
      iterations: 1,
      fieldMappings: 6,
      piiFlags: 2
    });
    expect(summary.mcpCalls).toBeGreaterThan(0);
  });

  it("summarizes the AppInspect loop for the lifecycle overview", () => {
    const summary = summarizeStage(appinspectEvents as ReplayEvent[]);
    expect(summary).toMatchObject({
      runStatus: "clean",
      initialFailures: 3,
      finalFailures: 0,
      healed: 3,
      mcpCalls: 0,
      fieldMappings: 0,
      piiFlags: 0
    });
  });
});

describe("buildAuditTrail", () => {
  it("builds one rich row per AppInspect provenance entry", () => {
    const provenance = parseProvenance(appinspectProvenanceRaw);
    const rows = buildAuditTrail(provenance, []);
    expect(rows).toHaveLength(3);
    expect(rows[0]).toMatchObject({
      iteration: 1,
      failure: "check_that_local_does_not_exist (local/)",
      result: "pass",
      changedPaths: ["local/"]
    });
    expect(rows[0].diagnosis).toMatch(/local\//);
    expect(rows[0].rationale.length).toBeGreaterThan(0);
  });

  it("carries the onboarding diagnosis, rationale, and changed paths", () => {
    const provenance = parseProvenance(onboardingProvenanceRaw);
    const rows = buildAuditTrail(provenance, []);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      iteration: 1,
      result: "pass",
      changedPaths: ["onboarding/candidate-01.spl"]
    });
    expect(rows[0].diagnosis.length).toBeGreaterThan(0);
    expect(rows[0].patch.length).toBeGreaterThan(0);
  });

  it("falls back to replay ledger entries when no provenance is present", () => {
    const ledgerEntries: LedgerEntryEvent[] = [
      {
        type: "ledger_entry",
        ts: "2026-06-04T00:00:07Z",
        stage: "appinspect",
        iteration: 2,
        failure: "check_user_seed_conf_deny_list (default/user-seed.conf)",
        diagnosis: "ships user-seed.conf",
        patch: "removed user-seed.conf",
        rationale: "credentials belong to Splunk auth",
        result: "pass",
        failure_id: "f2",
        message: "seed exists"
      }
    ];
    const rows = buildAuditTrail([], ledgerEntries);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      iteration: 2,
      patch: "removed user-seed.conf",
      result: "pass",
      changedPaths: [],
      timestamp: "2026-06-04T00:00:07Z"
    });
  });

  it("returns an empty trail when there is nothing to show", () => {
    expect(buildAuditTrail([], [])).toEqual([]);
  });
});

describe("formatLedgerTimestamp", () => {
  it("extracts the compact time from an ISO timestamp", () => {
    expect(formatLedgerTimestamp("2026-06-04T08:46:29Z")).toBe("08:46:29Z");
  });

  it("returns an empty string for a null timestamp", () => {
    expect(formatLedgerTimestamp(null)).toBe("");
  });
});
