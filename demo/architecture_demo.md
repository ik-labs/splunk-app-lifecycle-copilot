# Architecture — Demo Walkthrough (Technical)

A presentation-ready, technical view of the Splunk App Lifecycle Copilot for the
demo. Every box and arrow maps to real code; module/function names are cited so
the diagrams can be defended live. For the required hackathon artifact see
[`../architecture_diagram.md`](../architecture_diagram.md).

**Thesis:** one artifact-agnostic self-heal engine
(`diagnose → select deterministic patch → apply → re-validate`) drives **three**
loops; the LLM writes diagnosis/rationale *text only*, deterministic patch
functions make every change, and every decision is appended to a provenance
ledger.

---

## 1. System overview

```mermaid
flowchart TB
    DEV["Developer / CI<br/>copilot CLI · VS Code task"]

    subgraph PKG["lifecycle_copilot (Python 3.13)"]
        ENGINE["SelfHealEngine<br/>self_heal.py<br/>diagnose → select → patch → re-validate (capped)"]
        REC["EventRecorder<br/>events.py · events.jsonl + on_event hook"]
        LEDGER["ProvenanceLedger<br/>provenance.py · append-only JSONL"]

        subgraph LOOPS["Loops (validate + patch registry differ)"]
            ONB["Stage 1 · Onboarding<br/>onboarding/loop.py"]
            AIN["Stage 2 · AppInspect<br/>appinspect/loop.py"]
            SPL["Stage 4 · SPL Lint<br/>spl_lint/loop.py"]
        end

        SRV["SSE server · server.py<br/>Starlette · /api/stream"]
    end

    subgraph SPLUNK["Splunk Enterprise (Docker)"]
        HEC["HEC :8088"]
        MCP["MCP Server :8089<br/>splunk_run_query"]
        IDX["Index + CIM data models"]
    end

    AINSPECT["splunk-appinspect CLI<br/>local static analysis"]
    RULESET["SPL cost ruleset<br/>spl_lint/rules.py"]

    subgraph UI["Dashboard (React + Vite + Bun)"]
        REDUCER["deriveReplayState reducer<br/>lib/replay.ts"]
        REPLAY["Replay (committed demo JSON)"]
        LIVE["Live (EventSource · lib/liveStream.ts)"]
    end

    DEV --> ONB & AIN & SPL
    ONB & AIN & SPL --> ENGINE
    ENGINE --> REC --> LEDGER

    ONB -->|HEC ingest| HEC
    ONB -->|validate inline SPL| MCP
    HEC --> IDX
    MCP --> IDX
    AIN --> AINSPECT
    SPL --> RULESET

    REC -.->|events.json| REPLAY
    SRV -->|SSE loop_event| LIVE
    AIN -.->|live| SRV
    SPL -.->|live| SRV
    REPLAY & LIVE --> REDUCER
    LEDGER --> DEV
```

The engine, recorder, and ledger are shared infrastructure. Each loop differs in
exactly two injected callables: how it **validates** and which **patchers** it
selects from.

---

## 2. Shared self-heal engine (the spine)

`SelfHealEngine.run()` (`self_heal.py`) is one loop, parametrized per stage:

```mermaid
sequenceDiagram
    participant L as Loop (onboarding/appinspect/spl_lint)
    participant E as SelfHealEngine
    participant V as validate(iteration)
    participant D as diagnose(failure)  ← LLM text only
    participant P as apply_patch(failure)  ← deterministic
    participant R as EventRecorder / ProvenanceLedger

    L->>E: run()
    E->>R: emit run_started
    E->>V: validate(0)
    V-->>E: ValidationResult{failures, summary}
    E->>R: emit failure_detected (×N)
    loop until is_clean or max_iters
        E->>E: select_failure(failures)  (priority order)
        E->>D: diagnose(failure)
        D-->>E: {text, rationale}
        E->>R: emit diagnosis
        E->>P: apply_patch(failure)
        P-->>E: PatchResult{summary, changed_paths}
        E->>R: emit patch_applied
        E->>V: validate(iteration)
        V-->>E: ValidationResult
        E->>R: emit revalidated{pass|fail} + ledger_entry
    end
    E->>R: emit run_complete{status, iterations}
```

`ValidationResult.is_clean` ⇔ `summary.failure == 0 and summary.error == 0`.
The patch registry is a constrained dict (`PATCHERS` per loop); there is no
free-form file editing — that is what keeps runs reproducible and the audit
trail defensible.

| Loop | `validate` source | `select_failure` / patchers | Live Splunk? |
|---|---|---|---|
| Onboarding | `splunk_run_query` over indexed events (MCP) | swap inline `rex`/`eval` candidate | **Yes** |
| AppInspect | `splunk-appinspect inspect --data-format json` | remove `local/`, `user-seed.conf`, `outputs.conf` | No |
| SPL Lint | `lint_spl()` cost ruleset | `index=main` / `earliest=-24h` / `\| sort 1000` rewrites | No |

---

## 3. Onboarding loop — live MCP data flow

The bonus-prize path. `splunk_run_query` is the validation oracle the loop
iterates against, not a one-shot call.

```mermaid
sequenceDiagram
    participant OL as OnboardingLoop
    participant HEC as Splunk HEC :8088
    participant MCP as Splunk MCP Server :8089
    participant IDX as Index (main)

    OL->>HEC: ingest 150 raw UPI events (hec.py)
    HEC->>IDX: index events
    loop settle (bounded)
        OL->>MCP: splunk_run_query "stats count" (purpose=index_settle)
        MCP->>IDX: search
        MCP-->>OL: count → emit mcp_tool_call
    end
    Note over OL: candidate-00 inline rex/eval + CIM aliases
    OL->>MCP: splunk_run_query "candidate-00 | table ..."
    MCP-->>OL: extracted fields → 3 gaps (timestamp / CIM / PII)
    Note over OL: diagnose → swap to candidate-01 (deterministic)
    OL->>MCP: splunk_run_query "candidate-01 | table ..."
    MCP-->>OL: extracted fields → clean
    Note over OL: emit field_extracted x6, pii_flagged x2, ledger_entry
```

Verified live run (this build): **150 events ingested · 6 real `splunk_run_query`
calls · 3 gaps → 0 · 6 CIM mappings** (`amt→amount`, `status→action`,
`vpa→dest`, `payer_vpa→src_user`, `txn_id→transaction_id`, `gstin→vendor_id`)
**· 2 PII flags** (`payer_vpa`, `payer_mobile`). Auth uses the RSA-encrypted MCP
token (`mcp_client.py`), not a REST bearer token; the loop hard-fails if
`splunk_run_query` is unavailable.

---

## 4. Live mode — SSE streaming runtime

"Go Live" streams a static loop's events as it executes, rendered through the
*same* reducer as replay. Only the event source differs.

```mermaid
sequenceDiagram
    participant B as Browser (lib/liveStream.ts)
    participant S as Starlette /api/stream (server.py)
    participant Q as asyncio.Queue
    participant T as worker thread
    participant LP as AppInspect / SPL Lint loop
    participant Rec as EventRecorder.on_event

    B->>S: EventSource GET /api/stream?loop=spl_lint
    S->>T: thread(target=worker)
    T->>LP: run(event_sink=sink)
    LP->>Rec: emit(event)
    Rec->>S: sink(event) → loop.call_soon_threadsafe(Q.put_nowait)
    loop per event
        S->>Q: await get()
        S-->>B: SSE "loop_event" {json}  (paced by ?delay)
        B->>B: append → deriveReplayState(events, last)
    end
    T-->>S: sentinel None (run finished)
    S-->>B: SSE "loop_done"
    B->>B: render Live · done · Clean
```

The `on_event` hook (`events.py`) is best-effort and wrapped in try/except so a
streaming subscriber can never break a run. Only the static loops are exposed
live (`LIVE_LOOPS = ("appinspect", "spl_lint")`) — both need no Splunk, so the
live demo is dependency-free. CORS is open for the dev origin; `VITE_LIVE_URL`
overrides the default `http://127.0.0.1:8765`.

---

## 5. Module map

```mermaid
flowchart LR
    subgraph py["src/lifecycle_copilot/"]
        cli["cli.py — copilot {onboard,appinspect,lint,serve}"]
        sh["self_heal.py — SelfHealEngine"]
        ev["events.py — EventRecorder (+on_event)"]
        pv["provenance.py — ProvenanceLedger"]
        dg["diagnosis.py — Diagnosis / templates"]
        srv["server.py — SSE app"]
        subgraph onb["onboarding/"]
            o1["loop.py · hec.py · mcp_client.py"]
            o2["candidates.py · validator.py · models.py · patchers.py"]
        end
        subgraph ains["appinspect/"]
            a1["loop.py · runner.py · parser.py · patchers.py"]
        end
        subgraph spl["spl_lint/"]
            s1["loop.py · rules.py · patchers.py"]
        end
    end

    subgraph ui["ui/dashboard/src/"]
        app["App.tsx — stages, overview, live toggle"]
        rp["lib/replay.ts — deriveReplayState, buildAuditTrail"]
        ls["lib/liveStream.ts — EventSource client"]
        dm["data/demo.ts — committed STAGES"]
    end

    cli --> onb & ains & spl & srv
    onb & ains & spl --> sh --> ev & pv
    srv --> ains & spl
    app --> rp & ls
    dm --> rp
```

Tests: **32 Python** (`tests/`) + **18 dashboard** (`lib/replay.test.ts`), ruff
clean, dashboard `tsc` + `vite build` green.

---

## 6. Event & provenance contract

Every loop emits the same event vocabulary to `events.jsonl` (streamed live via
`on_event`, snapshotted to `events.json` for replay):

`run_started · failure_detected · diagnosis · patch_applied · revalidated ·
ledger_entry · run_complete` — plus onboarding-only `mcp_tool_call`,
`field_extracted`, `pii_flagged`.

Provenance ledger entry (`provenance.jsonl`, one per patch — the "remember"):

```json
{
  "stage": "spl_lint", "iteration": 1,
  "failure": "spl_wildcard_index (costly_search.spl)",
  "diagnosis": "...", "patch": "...", "rationale": "...",
  "validation_result": "pass", "timestamp": "2026-06-13T...Z",
  "failure_id": "spl_lint:spl_wildcard_index",
  "check": "spl_wildcard_index", "file": "costly_search.spl",
  "line": 1, "message": "...", "changed_paths": ["costly_search.spl"]
}
```

The dashboard's Provenance Ledger panel renders this directly
(`buildAuditTrail`), so "trust the fix" and "what the agent did" are the same
artifact.

---

## 7. Stack

| Layer | Tech |
|---|---|
| Agent / loops | Python 3.13, `splunklib` SDK, `mcp` client, `splunk-appinspect` |
| Splunk | `splunk/splunk:latest` (Docker), HEC, Splunk MCP Server app (encrypted token) |
| Live server | Starlette + `sse-starlette`, `uvicorn`, background thread + `asyncio.Queue` |
| Dashboard | React + TypeScript + Vite + Bun, pure reducer, `EventSource` |
| Quality | `pytest`, `ruff`, `vitest`, Playwright (manual responsive checks) |

> Roadmap (architecture-only): Stage 3 scaffold + test-data generation, Stage 5
> Simple XML → Dashboard Studio migration — both target the same engine.
