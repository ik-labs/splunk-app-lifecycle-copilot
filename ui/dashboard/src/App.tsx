import {
  Activity,
  AlertCircle,
  Check,
  CheckCircle2,
  FileJson,
  FolderOpen,
  Gauge,
  Info,
  Network,
  Pause,
  Play,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  SkipBack,
  Upload,
  Workflow
} from "lucide-react";
import { ChangeEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";

import { DEFAULT_STAGE, STAGE_ORDER, STAGES, type StageArtifact } from "./data/demo";
import {
  EVENT_SPACING_MS,
  deriveReplayState,
  formatReplayTime,
  getActiveIndex,
  getTotalDuration
} from "./lib/replay";
import type {
  FailureReplayState,
  FieldMapping,
  LoopName,
  ProvenanceEntry,
  ReplayEvent,
  ReplayViewState
} from "./types";

const speeds = [0.5, 1, 1.5, 2];

export default function App() {
  const [stage, setStage] = useState<LoopName>(DEFAULT_STAGE);
  const [uploadedEvents, setUploadedEvents] = useState<ReplayEvent[] | null>(null);
  const [elapsedMs, setElapsedMs] = useState(() => getTotalDuration(STAGES[DEFAULT_STAGE].events));
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [selectedFailureId, setSelectedFailureId] = useState<string | null>(null);
  const lastTickRef = useRef<number | null>(null);

  const dataset = STAGES[stage];
  const events = uploadedEvents ?? dataset.events;
  const provenance = uploadedEvents ? [] : dataset.provenance;
  const artifacts = dataset.artifacts;
  const hasFieldEvents = useMemo(
    () => events.some((event) => event.type === "field_extracted"),
    [events]
  );

  const totalDuration = useMemo(() => getTotalDuration(events), [events]);
  const activeIndex = getActiveIndex(events, elapsedMs);
  const replayState = useMemo(() => deriveReplayState(events, activeIndex), [events, activeIndex]);
  const selectedFailure =
    replayState.failures.find(
      (failure) => failure.failureId === (selectedFailureId ?? replayState.activeFailureId)
    ) ?? replayState.failures.at(0);

  useEffect(() => {
    if (!playing) {
      lastTickRef.current = null;
      return;
    }

    let frame = 0;
    const tick = (now: number) => {
      if (lastTickRef.current === null) {
        lastTickRef.current = now;
      }
      const delta = (now - lastTickRef.current) * speed;
      lastTickRef.current = now;

      setElapsedMs((current) => {
        const next = Math.min(totalDuration, current + delta);
        if (next >= totalDuration) {
          setPlaying(false);
        }
        return next;
      });
      frame = window.requestAnimationFrame(tick);
    };

    frame = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frame);
  }, [playing, speed, totalDuration]);

  const handlePlayPause = () => {
    if (playing) {
      setPlaying(false);
      return;
    }
    if (elapsedMs >= totalDuration) {
      setElapsedMs(0);
    }
    setPlaying(true);
  };

  const handleRestart = () => {
    setElapsedMs(0);
    setPlaying(true);
  };

  const handleScrub = (value: string) => {
    setPlaying(false);
    setElapsedMs(Number(value) * EVENT_SPACING_MS);
  };

  const handleSelectStage = (next: LoopName) => {
    if (next === stage && !uploadedEvents) {
      return;
    }
    setStage(next);
    setUploadedEvents(null);
    setElapsedMs(getTotalDuration(STAGES[next].events));
    setPlaying(false);
    setSelectedFailureId(null);
  };

  const handleUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    try {
      const parsed = JSON.parse(await file.text()) as ReplayEvent[];
      if (!Array.isArray(parsed)) {
        throw new Error("Expected an array of replay events.");
      }
      setUploadedEvents(parsed);
      setElapsedMs(getTotalDuration(parsed));
      setPlaying(false);
      setSelectedFailureId(null);
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Could not load replay JSON.");
    } finally {
      event.target.value = "";
    }
  };

  return (
    <div className="app-shell">
      <Sidebar activeStage={uploadedEvents ? null : stage} onSelectStage={handleSelectStage} />
      <main className="workspace">
        <TopBar
          activeIndex={activeIndex}
          eventCount={events.length}
          elapsedMs={elapsedMs}
          onPlayPause={handlePlayPause}
          onRestart={handleRestart}
          onScrub={handleScrub}
          onUpload={handleUpload}
          playing={playing}
          replayState={replayState}
          speed={speed}
          tagline={uploadedEvents ? "Uploaded replay" : dataset.tagline}
          totalDuration={totalDuration}
          setSpeed={setSpeed}
        />

        <section className="metrics-grid" aria-label="Run metrics">
          <MetricCard
            icon={<AlertCircle />}
            label="Initial failures"
            tone="danger"
            value={replayState.metrics.initialFailures}
          />
          <MetricCard
            icon={<CheckCircle2 />}
            label="Healed"
            tone="success"
            value={replayState.metrics.healed}
          />
          <MetricCard
            icon={<RotateCcw />}
            label="Iterations"
            tone="info"
            value={replayState.metrics.iterations}
          />
          <MetricCard
            icon={<ShieldCheck />}
            label="Final failures"
            tone="success"
            value={replayState.metrics.finalFailures}
          />
          <MetricCard
            icon={<Network />}
            label="MCP tool calls"
            tone="info"
            value={replayState.metrics.mcpCalls}
          />
        </section>

        <section className="content-grid">
          <TimelinePanel
            activeFailureId={selectedFailure?.failureId ?? replayState.activeFailureId}
            failures={replayState.failures}
            onSelect={setSelectedFailureId}
            subtitle={dataset.tagline}
          />
          <LedgerPanel ledgerEntries={replayState.ledgerEntries} provenance={provenance} />
          {hasFieldEvents ? (
            <CimMappingPanel
              fieldMappings={replayState.fieldMappings}
              piiFlags={replayState.piiFlags}
            />
          ) : null}
          <ArtifactsPanel artifacts={artifacts} label={dataset.artifactsLabel} />
          <EventStreamPanel
            activeEvent={replayState.activeEvent}
            events={replayState.visibleEvents}
            totalEvents={events.length}
            wide={hasFieldEvents}
          />
        </section>
      </main>
    </div>
  );
}

interface SidebarProps {
  activeStage: LoopName | null;
  onSelectStage: (stage: LoopName) => void;
}

function Sidebar({ activeStage, onSelectStage }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">&gt;</div>
        <div>
          <strong>Splunk App Lifecycle Copilot</strong>
          <span>Replay Console</span>
        </div>
      </div>

      <nav className="stage-nav" aria-label="Lifecycle stages">
        {STAGE_ORDER.map((loop) => {
          const stageData = STAGES[loop];
          const isActive = loop === activeStage;
          return (
            <button
              className={`stage-item ${isActive ? "active" : ""}`}
              type="button"
              key={loop}
              onClick={() => onSelectStage(loop)}
              aria-pressed={isActive}
            >
              <span className="stage-index">{stageData.index}</span>
              <span>
                <strong>{stageData.label}</strong>
                <small>{isActive ? "Active replay" : "Switch replay"}</small>
              </span>
              {loop === "onboarding" ? <Network size={18} /> : <Activity size={18} />}
            </button>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <span>Dual-stage self-heal replay</span>
        <span>Committed demo events — no live Splunk required</span>
      </div>
    </aside>
  );
}

interface TopBarProps {
  activeIndex: number;
  eventCount: number;
  elapsedMs: number;
  onPlayPause: () => void;
  onRestart: () => void;
  onScrub: (value: string) => void;
  onUpload: (event: ChangeEvent<HTMLInputElement>) => void;
  playing: boolean;
  replayState: ReplayViewState;
  speed: number;
  tagline: string;
  totalDuration: number;
  setSpeed: (speed: number) => void;
}

function TopBar({
  activeIndex,
  eventCount,
  elapsedMs,
  onPlayPause,
  onRestart,
  onScrub,
  onUpload,
  playing,
  replayState,
  speed,
  tagline,
  totalDuration,
  setSpeed
}: TopBarProps) {
  return (
    <header className="topbar">
      <div className="title-block">
        <div>
          <h1>Replay Mode</h1>
          <p>{tagline}</p>
        </div>
        <span className="live-dot" aria-label="Replay data loaded" />
      </div>

      <div className="transport" aria-label="Replay controls">
        <button className="icon-button" type="button" onClick={onRestart} aria-label="Restart replay">
          <SkipBack size={18} />
        </button>
        <button className="icon-button primary" type="button" onClick={onPlayPause}>
          {playing ? <Pause size={18} /> : <Play size={18} />}
          <span>{playing ? "Pause" : "Play"}</span>
        </button>
        <span className="timecode">{formatReplayTime(elapsedMs)}</span>
        <input
          aria-label="Replay position"
          className="scrubber"
          max={Math.max(0, eventCount - 1)}
          min={0}
          onChange={(event) => onScrub(event.target.value)}
          step={1}
          type="range"
          value={Math.max(0, activeIndex)}
        />
        <span className="timecode muted">{formatReplayTime(totalDuration)}</span>
      </div>

      <div className="topbar-actions">
        <label className="upload-button">
          <Upload size={16} />
          Load events
          <input accept="application/json,.json" type="file" onChange={onUpload} />
        </label>
        <label className="speed-select">
          <span>Speed</span>
          <select value={speed} onChange={(event) => setSpeed(Number(event.target.value))}>
            {speeds.map((value) => (
              <option key={value} value={value}>
                {value.toFixed(1)}x
              </option>
            ))}
          </select>
        </label>
        <div className={`status-chip ${replayState.runStatus}`}>
          <Check size={16} />
          {replayState.runStatus === "clean" ? "Clean" : replayState.runStatus}
        </div>
        <Info className="info-icon" size={20} aria-label="Replay info" />
      </div>
    </header>
  );
}

interface MetricCardProps {
  icon: ReactNode;
  label: string;
  tone: "danger" | "success" | "info";
  value: number;
}

function MetricCard({ icon, label, tone, value }: MetricCardProps) {
  return (
    <article className="metric-card">
      <div className={`metric-icon ${tone}`}>{icon}</div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </article>
  );
}

interface TimelinePanelProps {
  activeFailureId: string | null;
  failures: FailureReplayState[];
  onSelect: (failureId: string) => void;
  subtitle: string;
}

function TimelinePanel({ activeFailureId, failures, onSelect, subtitle }: TimelinePanelProps) {
  return (
    <section className="panel timeline-panel">
      <PanelHeader
        title="Self-Heal Timeline"
        subtitle={subtitle}
        icon={<Gauge size={18} />}
      />
      <div className="timeline-tracks">
        {failures.map((failure, index) => (
          <TimelineCard
            failure={failure}
            index={index}
            isActive={failure.failureId === activeFailureId}
            key={failure.failureId}
            onSelect={() => onSelect(failure.failureId)}
          />
        ))}
      </div>
      <div className="legend">
        <span>
          <i className="legend-dot danger" />
          Detected
        </span>
        <span>
          <i className="legend-dot warn" />
          Diagnosed / patched
        </span>
        <span>
          <i className="legend-dot success" />
          Revalidated
        </span>
      </div>
    </section>
  );
}

interface TimelineCardProps {
  failure: FailureReplayState;
  index: number;
  isActive: boolean;
  onSelect: () => void;
}

function TimelineCard({ failure, index, isActive, onSelect }: TimelineCardProps) {
  return (
    <button className={`timeline-card ${isActive ? "selected" : ""}`} type="button" onClick={onSelect}>
      <div className="timeline-card-header">
        <strong>Iteration {failure.iteration ?? index + 1}</strong>
        <span className={failure.revalidated === "pass" ? "mini-chip pass" : "mini-chip fail"}>
          {failure.revalidated === "pass" ? "Passed" : "Open"}
        </span>
      </div>
      <code>{failure.file}</code>
      <StepRow number={1} label="Detect" state={failure.detected ? "failed" : "pending"} />
      <StepRow number={2} label="Diagnose" state={failure.diagnosed ? "progress" : "pending"} />
      <StepRow number={3} label="Patch" state={failure.patched ? "patched" : "pending"} />
      <StepRow
        number={4}
        label="Revalidate"
        state={failure.revalidated === "pass" ? "passed" : failure.revalidated === "fail" ? "failed" : "pending"}
      />
      <p>{failure.patch ?? failure.message}</p>
    </button>
  );
}

function StepRow({
  label,
  number,
  state
}: {
  label: string;
  number: number;
  state: "pending" | "failed" | "progress" | "patched" | "passed";
}) {
  return (
    <div className={`step-row ${state}`}>
      <span className="step-number">{number}</span>
      <span>{label}</span>
      <strong>{state === "progress" ? "In review" : state}</strong>
    </div>
  );
}

function LedgerPanel({
  ledgerEntries,
  provenance
}: {
  ledgerEntries: ReplayViewState["ledgerEntries"];
  provenance: ProvenanceEntry[];
}) {
  const fallbackEntries = ledgerEntries.length > 0 ? ledgerEntries : [];
  return (
    <section className="panel ledger-panel">
      <PanelHeader
        title="Provenance Ledger"
        subtitle={`${provenance.length || ledgerEntries.length} entries`}
        icon={<ShieldCheck size={18} />}
      />
      <div className="ledger-list">
        {fallbackEntries.length === 0 ? (
          <p className="empty-state">Replay has not reached a persisted decision yet.</p>
        ) : (
          fallbackEntries.map((entry) => (
            <article className="ledger-row" key={`${entry.failure_id}-${entry.iteration}`}>
              <div className="ledger-row-top">
                <span className="iteration-pill">I{entry.iteration}</span>
                <strong>{entry.patch}</strong>
                <span className="result-pass">{entry.result}</span>
              </div>
              <code>{entry.failure}</code>
              <p>{entry.rationale}</p>
            </article>
          ))
        )}
      </div>
    </section>
  );
}

function ArtifactsPanel({ artifacts, label }: { artifacts: StageArtifact[]; label: string }) {
  return (
    <section className="panel artifacts-panel">
      <PanelHeader title="Artifacts" subtitle={label} icon={<FolderOpen size={18} />} />
      <div className="artifact-table">
        {artifacts.map((row) => (
          <div className="artifact-row" key={row.path}>
            <FileJson size={16} />
            <span className={`artifact-status ${row.status}`}>{row.type}</span>
            <code>{row.path}</code>
          </div>
        ))}
      </div>
    </section>
  );
}

function CimMappingPanel({
  fieldMappings,
  piiFlags
}: {
  fieldMappings: FieldMapping[];
  piiFlags: string[];
}) {
  return (
    <section className="panel cim-panel">
      <PanelHeader
        title="CIM Mapping & PII"
        subtitle={`${fieldMappings.length} mapped · ${piiFlags.length} PII`}
        icon={<Workflow size={18} />}
      />
      {fieldMappings.length === 0 ? (
        <p className="empty-state">No CIM mappings verified yet.</p>
      ) : (
        <div className="cim-list">
          {fieldMappings.map((mapping) => (
            <div className="cim-row" key={mapping.cim}>
              <code>{mapping.raw}</code>
              <span className="cim-arrow">→</span>
              <code>{mapping.cim}</code>
              {piiFlags.includes(mapping.raw) ? (
                <span className="pii-chip">
                  <ShieldAlert size={13} />
                  PII
                </span>
              ) : (
                <span className="cim-spacer" />
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function EventStreamPanel({
  activeEvent,
  events,
  totalEvents,
  wide
}: {
  activeEvent: ReplayEvent | null;
  events: ReplayEvent[];
  totalEvents: number;
  wide: boolean;
}) {
  return (
    <section className={`panel event-panel ${wide ? "event-panel--wide" : ""}`}>
      <PanelHeader
        title="Event Stream"
        subtitle={`${events.length} / ${totalEvents} events`}
        icon={<Activity size={18} />}
      />
      <div className="event-stream">
        {events.slice(-9).map((event, index) => (
          <div className={`event-row ${event === activeEvent ? "active" : ""}`} key={`${event.ts}-${index}`}>
            <span>{indexLabel(events.length - Math.min(events.length, 9) + index)}</span>
            <strong>{event.type}</strong>
            <code>{eventSummary(event)}</code>
          </div>
        ))}
      </div>
      {activeEvent ? (
        <pre className="event-json">{JSON.stringify(activeEvent, null, 2)}</pre>
      ) : (
        <p className="empty-state">No replay events visible yet.</p>
      )}
    </section>
  );
}

function PanelHeader({
  icon,
  subtitle,
  title
}: {
  icon: ReactNode;
  subtitle: string;
  title: string;
}) {
  return (
    <header className="panel-header">
      <div className="panel-title">
        {icon}
        <h2>{title}</h2>
        <span>{subtitle}</span>
      </div>
    </header>
  );
}

function indexLabel(index: number): string {
  return `#${(index + 1).toString().padStart(2, "0")}`;
}

function eventSummary(event: ReplayEvent): string {
  if (event.type === "field_extracted") {
    return `${event.raw_field} → ${event.cim_field}`;
  }
  if (event.type === "pii_flagged") {
    return `PII: ${event.field}`;
  }
  if (event.type === "mcp_tool_call") {
    const detail = event.purpose ?? event.candidate_id ?? event.tool;
    return `${event.tool} · ${event.status}${detail && detail !== event.tool ? ` (${detail})` : ""}`;
  }
  if ("file" in event && typeof event.file === "string") {
    return event.file;
  }
  if ("failure_id" in event && typeof event.failure_id === "string") {
    return event.failure_id;
  }
  if ("status" in event && typeof event.status === "string") {
    return event.status;
  }
  return event.ts;
}
