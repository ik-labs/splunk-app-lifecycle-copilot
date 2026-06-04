import {
  Activity,
  AlertCircle,
  Check,
  CheckCircle2,
  Circle,
  FileJson,
  FolderOpen,
  Gauge,
  Info,
  Pause,
  Play,
  RotateCcw,
  ShieldCheck,
  SkipBack,
  Upload
} from "lucide-react";
import { ChangeEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";

import { artifactRows, initialEvents, initialProvenance } from "./data/demo";
import {
  EVENT_SPACING_MS,
  deriveReplayState,
  formatReplayTime,
  getActiveIndex,
  getTotalDuration
} from "./lib/replay";
import type { FailureReplayState, ProvenanceEntry, ReplayEvent, ReplayViewState } from "./types";

const speeds = [0.5, 1, 1.5, 2];

export default function App() {
  const [events, setEvents] = useState<ReplayEvent[]>(initialEvents);
  const [provenance, setProvenance] = useState<ProvenanceEntry[]>(initialProvenance);
  const [elapsedMs, setElapsedMs] = useState(() => getTotalDuration(initialEvents));
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [selectedFailureId, setSelectedFailureId] = useState<string | null>(null);
  const lastTickRef = useRef<number | null>(null);

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

  const handleUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    try {
      const uploadedEvents = JSON.parse(await file.text()) as ReplayEvent[];
      if (!Array.isArray(uploadedEvents)) {
        throw new Error("Expected an array of replay events.");
      }
      setEvents(uploadedEvents);
      setProvenance([]);
      setElapsedMs(getTotalDuration(uploadedEvents));
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
      <Sidebar />
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
        </section>

        <section className="content-grid">
          <TimelinePanel
            activeFailureId={selectedFailure?.failureId ?? replayState.activeFailureId}
            failures={replayState.failures}
            onSelect={setSelectedFailureId}
          />
          <LedgerPanel ledgerEntries={replayState.ledgerEntries} provenance={provenance} />
          <ArtifactsPanel />
          <EventStreamPanel
            activeEvent={replayState.activeEvent}
            events={replayState.visibleEvents}
            totalEvents={events.length}
          />
        </section>
      </main>
    </div>
  );
}

function Sidebar() {
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
        <button className="stage-item active" type="button">
          <span className="stage-index">2</span>
          <span>
            <strong>AppInspect</strong>
            <small>Active replay</small>
          </span>
          <Activity size={18} />
        </button>
        <button className="stage-item disabled" type="button" disabled>
          <span className="stage-index">1</span>
          <span>
            <strong>Onboarding</strong>
            <small>Disabled / future</small>
          </span>
          <Circle size={16} />
        </button>
      </nav>

      <div className="sidebar-footer">
        <span>AppInspect-only milestone</span>
        <span>No MCP or Splunk instance required</span>
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
  totalDuration,
  setSpeed
}: TopBarProps) {
  return (
    <header className="topbar">
      <div className="title-block">
        <div>
          <h1>Replay Mode</h1>
          <p>AppInspect self-heal replay</p>
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
}

function TimelinePanel({ activeFailureId, failures, onSelect }: TimelinePanelProps) {
  return (
    <section className="panel timeline-panel">
      <PanelHeader
        title="Self-Heal Timeline"
        subtitle="AppInspect replay"
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

function ArtifactsPanel() {
  return (
    <section className="panel artifacts-panel">
      <PanelHeader title="Artifacts" subtitle="Generated by AppInspect loop" icon={<FolderOpen size={18} />} />
      <div className="artifact-table">
        {artifactRows.map((row) => (
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

function EventStreamPanel({
  activeEvent,
  events,
  totalEvents
}: {
  activeEvent: ReplayEvent | null;
  events: ReplayEvent[];
  totalEvents: number;
}) {
  return (
    <section className="panel event-panel">
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
