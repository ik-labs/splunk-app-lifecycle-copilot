# UX & Demo Plan — App Lifecycle Copilot

Companion to `SCOPE.md`. Covers the demo surfaces, build order, tech stack, the
agent↔UI event contract, and the video plan. Read `SCOPE.md` first for the
project scope and the two loops.

---

## 1. Why UX matters here

The hackathon judges on four equally-weighted criteria; one is **Design / UX**
("Is the user experience well thought out?"). A pure-CLI tool scores poorly on
25% of the total no matter how good the engineering is. The UX is not polish —
it's a quarter of the score.

The core design problem: the self-heal loops are the whole thesis, but loops are
*invisible* in a terminal. The job of the UI is to **make the invisible loop
visible** — diagnose → patch → re-validate → green, on screen, in real time.

## 2. Three surfaces, one agent

The three surfaces are not competing UIs. They are three entry points to the
same agent, framed as "we meet developers where they already work." Effort is
deliberately unequal — one hero, two thin touchpoints.

| Surface | Role | Finish | Share of UX budget |
|---|---|---|---|
| Web dashboard | **Hero** — carries the video, makes loops visible | High | ~65% |
| Terminal / CLI | "It's real software" proof; the agent's entry point | Clean | ~15% (mostly free) |
| IDE (VS Code) | Authenticity — fits the real dev workflow, mirrors Splunk's own MCP-in-IDE | Thin | ~20% |

**Anti-goal:** three half-built UIs. Even effort = three mediocre surfaces + a
thin agent, and judges see through it. One polished hero reads as "designed
across the workflow."

## 3. Build order (de-risked)

1. **Terminal CLI first** — nearly free, it's the agent entry point anyway.
   Wrap output in Python `rich`: spinners, colored pass/fail, final summary
   table. ~an afternoon.
2. **Web dashboard** — the bulk of the work. Build the WebSocket event stream
   first, then the four panels (loop cards, self-heal timeline, provenance
   ledger, cost/PII alerts).
3. **IDE touchpoint last** — a VS Code task that runs the CLI, or a minimal
   webview embedding the dashboard. Enough for a 10-second cutaway. Do NOT build
   a full extension unless everything else is done.

If time runs out, the terminal + dashboard alone is a complete, well-scored
demo. The IDE cutaway is the first thing to cut.

## 4. Tech stack

- **Dashboard:** React 19 + Vite. WebSocket to the Python agent.
- **Real-time:** agent emits events over a WebSocket; dashboard renders live.
  Same fanout pattern as prior real-time work — familiar territory.
- **Self-heal timeline:** the one component worth real polish. React Flow nodes
  for iteration cards are a good fit.
- **Terminal:** Python `rich`.
- **IDE:** VS Code task invoking the CLI, or a webview wrapping the dashboard.

## 5. Agent ↔ UI event contract

The agent and the dashboard agree on this event protocol. The agent emits these
over the WebSocket; the dashboard is a pure renderer of the stream. Locking this
early lets the agent and UI be built in parallel.

```
{ "type": "run_started",      "loop": "onboarding" | "appinspect", "ts": <iso> }
{ "type": "field_extracted",  "raw": "amt", "cim": "amount", "ts": <iso> }
{ "type": "pii_flagged",      "field": "payer_vpa", "ts": <iso> }
{ "type": "mcp_tool_call",    "tool": "splunk_run_query" | "splunk_get_knowledge_objects" | "saia_generate_spl" | "saia_explain_spl" | "saia_optimize_spl", "status": "started" | "succeeded" | "failed", "ts": <iso> }
{ "type": "failure_detected", "loop": ..., "check": "...", "file": "...", "line": <n>, "ts": <iso> }
{ "type": "diagnosis",        "failure_id": ..., "text": "...", "ts": <iso> }
{ "type": "patch_applied",    "failure_id": ..., "summary": "...", "ts": <iso> }
{ "type": "revalidated",      "failure_id": ..., "result": "pass" | "fail", "iteration": <n>, "ts": <iso> }
{ "type": "cost_alert",       "search": "...", "issue": "unbounded index=*", "suggestion": "...", "ts": <iso> }
{ "type": "ledger_entry",     "stage": ..., "iteration": <n>, "failure": "...", "diagnosis": "...", "patch": "...", "rationale": "...", "result": "...", "ts": <iso> }
{ "type": "run_complete",     "loop": ..., "status": "clean" | "capped", "iterations": <n>, "ts": <iso> }
```

Notes:
- `ledger_entry` is the canonical record; the provenance ledger persists these
  to JSON (see `SCOPE.md` §4.1). The dashboard's other event types are
  derivable views for live animation.
- Every event carries `ts` so the dashboard can show timing and so a saved event
  log can be replayed deterministically (see §7).
- MCP events use the official Splunk MCP tool names. The dashboard should make
  `splunk_run_query` calls visible during onboarding because that is the core
  bonus-prize proof point. `splunk_run_query` is bounded by the MCP server
  (about 1 minute and about 1000 returned events); the 150-line onboarding
  fixture is inside those limits.
- `saia_*` events are optional. They appear only when Splunk AI Assistant is
  installed. The onboarding loop must still demo successfully with
  `splunk_run_query` alone.

## 6. Dashboard panels (the hero surface)

Four panels, matching the mockup:
1. **Metric cards** — fields extracted, AppInspect failures, heal iterations,
   PII flagged. The top-line "is it working" glance.
2. **Two loop cards** — Stage 1 onboarding (field→CIM mappings, PII tags) and
   Stage 2 AppInspect (the three failures → green). Status badge each.
3. **Self-heal timeline** — detect → diagnose → patch → re-validate → clean,
   labelled as the *shared engine driving both loops*. This is the platform
   thesis made visual.
4. **Provenance ledger + cost/PII alerts** — ledger reads as decisions-with-
   rationale, not a log dump; alerts tie to the real researched pains (cost of
   unbounded scans, PII exposure).

## 7. Demo safety: replay mode

A live WebSocket demo can glitch on video. Mitigations:
- The dashboard supports a **replay mode**: play back a saved event log (a
  recorded run's events with their timestamps) deterministically.
- Replay mode doubles as a rehearsal tool for timing the video.
- Record a clean backup video regardless — the rules let judges score on the
  video alone.

## 8. The 3-minute video flow (surfaces mapped)

This refines `SCOPE.md` §10 with the surface for each beat.

- **0:00–0:15 — Terminal.** Developer types `copilot onboard sample_upi.log`.
  Authentic, fast. Establishes "real software."
- **0:15–1:10 — Dashboard (onboarding loop).** Cut to the hero. Fields light up
  as `splunk_run_query` validates inline `rex` / `eval` extraction candidates
  against real events, PII flag fires, CIM mapping resolves. Land: suggestion
  vs. *verified against real events*.
- **1:10–2:10 — Dashboard (AppInspect loop, hero shot).** Three red failures →
  `local/` config, `user-seed.conf`, and forbidden `outputs.conf` → deterministic
  patchers work each → red turns green. Most screen time. The visceral "it
  actually fixed it" moment.
- **2:10–2:25 — VS Code cutaway.** Same agent triggered from the IDE.
  "And it lives where you already work." ~10–15s.
- **2:25–2:45 — Dashboard (provenance + thesis).** One engine drove both loops;
  open the ledger — every decision with its rationale. Institutional memory.
- **2:45–3:00 — Close.** A week of expert-gated toil → an afternoon, with an
  audit trail. Name the MCP server's role (agent orchestrating real actions) to
  anchor the bonus prize. End on the repo URL.

**Throughout:** whenever the agent calls the MCP server, make the official tool
name visible on-screen (for example, `splunk_run_query` in the "MCP connected"
badge or call indicator). The MCP bonus judges are looking for the server
orchestrating meaningful actions — show the calls, don't hide them.

## 9. Repo additions (beyond SCOPE.md §6)

```
ui/
├── dashboard/            # React + Vite hero dashboard
│   ├── src/
│   │   ├── App.tsx
│   │   ├── ws.ts         # WebSocket client, parses the event contract
│   │   ├── panels/       # metrics, loop cards, timeline, ledger, alerts
│   │   └── replay.ts     # replay-mode event playback
│   └── package.json
├── cli/                  # rich-based terminal entry point
└── vscode/               # thin VS Code task / webview (build last)
demo/
├── recorded_events.json  # saved event log for replay mode
└── demo_script.md        # the §8 beat sheet
```
