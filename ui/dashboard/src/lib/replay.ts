import type {
  DiagnosisEvent,
  FailureDetectedEvent,
  FailureReplayState,
  FieldExtractedEvent,
  FieldMapping,
  LedgerEntryEvent,
  McpToolCallEvent,
  PatchAppliedEvent,
  PiiFlaggedEvent,
  ProvenanceEntry,
  ReplayEvent,
  ReplayMetrics,
  ReplayViewState,
  RevalidatedEvent,
  RunCompleteEvent
} from "../types";

export const EVENT_SPACING_MS = 900;

const PATCH_PRIORITY = [
  "check_that_local_does_not_exist",
  "check_user_seed_conf_deny_list",
  "check_if_outputs_conf_exists"
];

export function parseJsonl<T>(raw: string): T[] {
  return raw
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line) as T);
}

export function getTotalDuration(events: ReplayEvent[]): number {
  return Math.max(0, events.length - 1) * EVENT_SPACING_MS;
}

export function getActiveIndex(events: ReplayEvent[], elapsedMs: number): number {
  if (events.length === 0) {
    return -1;
  }
  return Math.min(events.length - 1, Math.max(0, Math.floor(elapsedMs / EVENT_SPACING_MS)));
}

export function deriveReplayState(events: ReplayEvent[], activeIndex: number): ReplayViewState {
  const safeIndex = events.length === 0 ? -1 : Math.min(Math.max(activeIndex, 0), events.length - 1);
  const visibleEvents = safeIndex >= 0 ? events.slice(0, safeIndex + 1) : [];
  const fullInitialFailureIds = getInitialFailureIds(events);
  const fullLedgerEntries = events.filter(isLedgerEntry);
  const visibleLedgerEntries = visibleEvents.filter(isLedgerEntry);
  const completeEvent = findLast(visibleEvents, isRunComplete);
  const cleanCompletion = completeEvent?.status === "clean";
  const failures = deriveFailures(events, visibleEvents, fullLedgerEntries, cleanCompletion);
  const metrics = deriveMetrics(fullInitialFailureIds, failures, visibleEvents, cleanCompletion);

  return {
    visibleEvents,
    fullInitialFailureIds,
    failures,
    ledgerEntries: visibleLedgerEntries,
    metrics,
    runStatus: completeEvent?.status ?? (visibleEvents.length > 0 ? "running" : "idle"),
    activeFailureId: getActiveFailureId(visibleEvents),
    activeEvent: visibleEvents.at(-1) ?? null,
    fieldMappings: getFieldMappings(visibleEvents),
    piiFlags: getPiiFlags(visibleEvents)
  };
}

export function parseProvenance(raw: string): ProvenanceEntry[] {
  return parseJsonl<ProvenanceEntry>(raw);
}

export interface StageSummary {
  runStatus: ReplayViewState["runStatus"];
  initialFailures: number;
  finalFailures: number;
  healed: number;
  iterations: number;
  mcpCalls: number;
  fieldMappings: number;
  piiFlags: number;
}

/** Collapse a full event stream into the final-state numbers shown in the
 * lifecycle overview. */
export function summarizeStage(events: ReplayEvent[]): StageSummary {
  const state = deriveReplayState(events, events.length - 1);
  return {
    runStatus: state.runStatus,
    initialFailures: state.metrics.initialFailures,
    finalFailures: state.metrics.finalFailures,
    healed: state.metrics.healed,
    iterations: state.metrics.iterations,
    mcpCalls: state.metrics.mcpCalls,
    fieldMappings: state.fieldMappings.length,
    piiFlags: state.piiFlags.length
  };
}

function deriveMetrics(
  initialFailureIds: string[],
  failures: FailureReplayState[],
  visibleEvents: ReplayEvent[],
  cleanCompletion: boolean
): ReplayMetrics {
  const initialFailures = initialFailureIds.length;
  // A clean run_complete means every detected gap is resolved, even when a
  // single onboarding patch heals several at once without per-failure events.
  const healed = cleanCompletion
    ? initialFailures
    : failures.filter((failure) => failure.revalidated === "pass").length;
  const iterations = Math.max(
    0,
    ...visibleEvents
      .map((event) => getIterationCount(event))
  );

  return {
    initialFailures,
    healed,
    iterations,
    finalFailures: Math.max(0, initialFailures - healed),
    mcpCalls: visibleEvents.filter(
      (event) => isMcpToolCall(event) && event.status === "started"
    ).length
  };
}

function deriveFailures(
  allEvents: ReplayEvent[],
  visibleEvents: ReplayEvent[],
  fullLedgerEntries: LedgerEntryEvent[],
  cleanCompletion: boolean
): FailureReplayState[] {
  const initialFailures = getInitialFailures(allEvents);
  const states = new Map<string, FailureReplayState>();

  for (const failure of initialFailures) {
    states.set(failure.failure_id, {
      failureId: failure.failure_id,
      check: failure.check,
      file: failure.file ?? "app",
      message: failure.message,
      iteration: getIterationForFailure(failure.failure_id, fullLedgerEntries),
      detected: false,
      diagnosed: false,
      patched: false,
      revalidated: null
    });
  }

  for (const event of visibleEvents) {
    if (isFailureDetected(event)) {
      ensureFailure(states, event);
      states.get(event.failure_id)!.detected = true;
    }

    if (isDiagnosis(event)) {
      ensureFailure(states, event);
      const failure = states.get(event.failure_id)!;
      failure.diagnosed = true;
      failure.diagnosis = event.text;
    }

    if (isPatchApplied(event)) {
      ensureFailure(states, event);
      const failure = states.get(event.failure_id)!;
      failure.patched = true;
      failure.patch = event.summary;
    }

    if (isRevalidated(event)) {
      ensureFailure(states, event);
      const failure = states.get(event.failure_id)!;
      failure.revalidated = event.result;
      failure.iteration = event.iteration;
    }

    if (isLedgerEntry(event)) {
      const failure = states.get(event.failure_id);
      if (failure) {
        failure.rationale = event.rationale;
      }
    }
  }

  if (cleanCompletion) {
    // Onboarding heals every detected gap with one deterministic candidate
    // swap, but only the selected gap emits diagnosis/patch/revalidate events.
    // Attribute that single fix to the still-open gaps so the timeline reads
    // as fully healed once the run is clean.
    const lastPatch = findLast(visibleEvents, isPatchApplied);
    const lastDiagnosis = findLast(visibleEvents, isDiagnosis);
    for (const failure of states.values()) {
      if (failure.revalidated === "pass") {
        continue;
      }
      failure.detected = true;
      failure.diagnosed = true;
      failure.patched = true;
      failure.revalidated = "pass";
      failure.diagnosis ??= lastDiagnosis?.text;
      failure.patch ??= lastPatch?.summary;
    }
  }

  return [...states.values()].sort(compareFailures);
}

function getInitialFailures(events: ReplayEvent[]): FailureDetectedEvent[] {
  const failures: FailureDetectedEvent[] = [];
  const seen = new Set<string>();
  for (const event of events) {
    // The initial batch ends once the self-heal loop starts acting on a
    // failure. Setup noise (run_started, and onboarding's leading
    // mcp_tool_call settle/query events) is skipped, not treated as the end.
    if (isHealingEvent(event)) {
      break;
    }
    if (isFailureDetected(event) && !seen.has(event.failure_id)) {
      seen.add(event.failure_id);
      failures.push(event);
    }
  }
  return failures;
}

function isHealingEvent(event: ReplayEvent): boolean {
  return (
    isDiagnosis(event) ||
    isPatchApplied(event) ||
    isRevalidated(event) ||
    isLedgerEntry(event) ||
    isRunComplete(event)
  );
}

function getFieldMappings(visibleEvents: ReplayEvent[]): FieldMapping[] {
  const mappings: FieldMapping[] = [];
  const seen = new Set<string>();
  for (const event of visibleEvents) {
    if (isFieldExtracted(event) && !seen.has(event.cim_field)) {
      seen.add(event.cim_field);
      mappings.push({ raw: event.raw_field, cim: event.cim_field });
    }
  }
  return mappings;
}

function getPiiFlags(visibleEvents: ReplayEvent[]): string[] {
  const flags: string[] = [];
  for (const event of visibleEvents) {
    if (isPiiFlagged(event) && !flags.includes(event.field)) {
      flags.push(event.field);
    }
  }
  return flags;
}

function getInitialFailureIds(events: ReplayEvent[]): string[] {
  return getInitialFailures(events).map((failure) => failure.failure_id);
}

function ensureFailure(
  states: Map<string, FailureReplayState>,
  event: FailureDetectedEvent | DiagnosisEvent | PatchAppliedEvent | RevalidatedEvent
): void {
  if (states.has(event.failure_id)) {
    return;
  }
  states.set(event.failure_id, {
    failureId: event.failure_id,
    check: event.check,
    file: event.file ?? "app",
    message: event.message,
    iteration: "iteration" in event ? event.iteration : null,
    detected: event.type !== "revalidated",
    diagnosed: false,
    patched: false,
    revalidated: null
  });
}

function getIterationForFailure(failureId: string, ledgerEntries: LedgerEntryEvent[]): number | null {
  return ledgerEntries.find((entry) => entry.failure_id === failureId)?.iteration ?? null;
}

function compareFailures(a: FailureReplayState, b: FailureReplayState): number {
  const aIteration = a.iteration ?? Number.POSITIVE_INFINITY;
  const bIteration = b.iteration ?? Number.POSITIVE_INFINITY;
  if (aIteration !== bIteration) {
    return aIteration - bIteration;
  }
  const aPriority = PATCH_PRIORITY.indexOf(a.check);
  const bPriority = PATCH_PRIORITY.indexOf(b.check);
  return normalizePriority(aPriority) - normalizePriority(bPriority);
}

function normalizePriority(priority: number): number {
  return priority === -1 ? Number.POSITIVE_INFINITY : priority;
}

function getActiveFailureId(visibleEvents: ReplayEvent[]): string | null {
  const active = visibleEvents
    .filter((event) => "failure_id" in event)
    .at(-1) as ReplayEvent & { failure_id?: string } | undefined;
  return active?.failure_id ?? null;
}

function isLedgerEntry(event: ReplayEvent): event is LedgerEntryEvent {
  return event.type === "ledger_entry";
}

function isRunComplete(event: ReplayEvent): event is RunCompleteEvent {
  return event.type === "run_complete";
}

function isFailureDetected(event: ReplayEvent): event is FailureDetectedEvent {
  return event.type === "failure_detected";
}

function isDiagnosis(event: ReplayEvent): event is DiagnosisEvent {
  return event.type === "diagnosis";
}

function isPatchApplied(event: ReplayEvent): event is PatchAppliedEvent {
  return event.type === "patch_applied";
}

function isRevalidated(event: ReplayEvent): event is RevalidatedEvent {
  return event.type === "revalidated";
}

function isMcpToolCall(event: ReplayEvent): event is McpToolCallEvent {
  return event.type === "mcp_tool_call";
}

function isFieldExtracted(event: ReplayEvent): event is FieldExtractedEvent {
  return event.type === "field_extracted";
}

function isPiiFlagged(event: ReplayEvent): event is PiiFlaggedEvent {
  return event.type === "pii_flagged";
}

function getIterationCount(event: ReplayEvent): number {
  if (isRevalidated(event) || isLedgerEntry(event)) {
    return event.iteration;
  }
  if (isRunComplete(event)) {
    return event.iterations;
  }
  return 0;
}

function findLast<T, S extends T>(items: T[], predicate: (item: T) => item is S): S | undefined {
  for (let index = items.length - 1; index >= 0; index -= 1) {
    const item = items[index];
    if (predicate(item)) {
      return item;
    }
  }
  return undefined;
}

export function formatReplayTime(ms: number): string {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
}
