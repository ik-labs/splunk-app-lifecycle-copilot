export type LoopName = "onboarding" | "appinspect";
export type RunStatus = "clean" | "capped";
export type ValidationStatus = "pass" | "fail";

interface BaseReplayEvent {
  type: string;
  ts: string;
}

export interface RunStartedEvent extends BaseReplayEvent {
  type: "run_started";
  loop: LoopName;
}

export interface FailureDetectedEvent extends BaseReplayEvent {
  type: "failure_detected";
  loop: LoopName;
  failure_id: string;
  check: string;
  file: string | null;
  line: number | null;
  message: string;
}

export interface DiagnosisEvent extends BaseReplayEvent {
  type: "diagnosis";
  failure_id: string;
  check: string;
  file: string | null;
  line: number | null;
  message: string;
  text: string;
}

export interface PatchAppliedEvent extends BaseReplayEvent {
  type: "patch_applied";
  failure_id: string;
  check: string;
  file: string | null;
  line: number | null;
  message: string;
  summary: string;
}

export interface RevalidatedEvent extends BaseReplayEvent {
  type: "revalidated";
  failure_id: string;
  check: string;
  file: string | null;
  line: number | null;
  message: string;
  result: ValidationStatus;
  iteration: number;
}

export interface LedgerEntryEvent extends BaseReplayEvent {
  type: "ledger_entry";
  stage: LoopName;
  iteration: number;
  failure: string;
  diagnosis: string;
  patch: string;
  rationale: string;
  result: ValidationStatus;
  failure_id: string;
  message: string;
}

export interface RunCompleteEvent extends BaseReplayEvent {
  type: "run_complete";
  loop: LoopName;
  status: RunStatus;
  iterations: number;
}

export interface UnknownReplayEvent extends BaseReplayEvent {
  type: string;
  [key: string]: unknown;
}

export type ReplayEvent =
  | RunStartedEvent
  | FailureDetectedEvent
  | DiagnosisEvent
  | PatchAppliedEvent
  | RevalidatedEvent
  | LedgerEntryEvent
  | RunCompleteEvent
  | UnknownReplayEvent;

export interface ProvenanceEntry {
  stage: LoopName;
  iteration: number;
  failure: string;
  diagnosis: string;
  patch: string;
  rationale: string;
  validation_result: ValidationStatus;
  timestamp: string;
  failure_id: string;
  check: string;
  file: string | null;
  line: number | null;
  message: string;
  changed_paths: string[];
}

export interface FailureReplayState {
  failureId: string;
  check: string;
  file: string;
  message: string;
  iteration: number | null;
  detected: boolean;
  diagnosed: boolean;
  patched: boolean;
  revalidated: ValidationStatus | null;
  diagnosis?: string;
  patch?: string;
  rationale?: string;
}

export interface ReplayMetrics {
  initialFailures: number;
  healed: number;
  iterations: number;
  finalFailures: number;
}

export interface ReplayViewState {
  visibleEvents: ReplayEvent[];
  fullInitialFailureIds: string[];
  failures: FailureReplayState[];
  ledgerEntries: LedgerEntryEvent[];
  metrics: ReplayMetrics;
  runStatus: RunStatus | "running" | "idle";
  activeFailureId: string | null;
  activeEvent: ReplayEvent | null;
}
