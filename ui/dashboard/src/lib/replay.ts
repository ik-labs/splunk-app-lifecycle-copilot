import type {
  DiagnosisEvent,
  FailureDetectedEvent,
  FailureReplayState,
  LedgerEntryEvent,
  PatchAppliedEvent,
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
  const failures = deriveFailures(events, visibleEvents, fullLedgerEntries);
  const completeEvent = findLast(visibleEvents, isRunComplete);
  const metrics = deriveMetrics(fullInitialFailureIds, failures, events);

  return {
    visibleEvents,
    fullInitialFailureIds,
    failures,
    ledgerEntries: visibleLedgerEntries,
    metrics,
    runStatus: completeEvent?.status ?? (visibleEvents.length > 0 ? "running" : "idle"),
    activeFailureId: getActiveFailureId(visibleEvents),
    activeEvent: visibleEvents.at(-1) ?? null
  };
}

export function parseProvenance(raw: string): ProvenanceEntry[] {
  return parseJsonl<ProvenanceEntry>(raw);
}

function deriveMetrics(
  initialFailureIds: string[],
  failures: FailureReplayState[],
  allEvents: ReplayEvent[]
): ReplayMetrics {
  const healed = failures.filter((failure) => failure.revalidated === "pass").length;
  const iterations = Math.max(
    0,
    ...allEvents
      .map((event) => getIterationCount(event))
  );

  return {
    initialFailures: initialFailureIds.length,
    healed,
    iterations,
    finalFailures: Math.max(0, initialFailureIds.length - healed)
  };
}

function deriveFailures(
  allEvents: ReplayEvent[],
  visibleEvents: ReplayEvent[],
  fullLedgerEntries: LedgerEntryEvent[]
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

  return [...states.values()].sort(compareFailures);
}

function getInitialFailures(events: ReplayEvent[]): FailureDetectedEvent[] {
  const failures: FailureDetectedEvent[] = [];
  const seen = new Set<string>();
  for (const event of events) {
    if (event.type !== "run_started" && event.type !== "failure_detected") {
      break;
    }
    if (isFailureDetected(event) && !seen.has(event.failure_id)) {
      seen.add(event.failure_id);
      failures.push(event);
    }
  }
  return failures;
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
