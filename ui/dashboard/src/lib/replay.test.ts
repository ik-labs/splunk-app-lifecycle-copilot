import { describe, expect, it } from "vitest";

import { deriveReplayState } from "./replay";
import type { ReplayEvent } from "../types";

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
