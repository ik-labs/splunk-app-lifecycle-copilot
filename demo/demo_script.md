# Demo Shot-List — Splunk App Lifecycle Copilot

Target length: **2:55** (hard cap 3:00). Judges may score on the video alone, so
record a clean backup take. Every time the agent calls the MCP server, keep it
on screen — the bonus prize rewards visible MCP orchestration.

Thesis line to land: **"Splunk's AI explains failures. This resolves, validates,
and remembers them."**

Flow: **terminal (three loops) → dashboard (overview + stages + provenance) →
live mode → close.** One shared self-heal engine, three working loops.

---

## Pre-roll setup (not recorded)

Do all of this before hitting record, so the live segment can't stall:

- [ ] `docker compose up -d` and wait for **healthy** (`docker inspect -f '{{.State.Health.Status}}' splunk-copilot`). First boot is ~1–2 min; a warm restart is ~45s. Only the **onboarding** loop needs Splunk — AppInspect and SPL lint are static.
- [ ] Confirm `.env` has a fresh `SPLUNK_MCP_ENCRYPTED_TOKEN` (token mint: `GET /services/mcp_token?username=admin&expires_on=%2B30d`). Optional: `.venv/bin/python smoke_test.py` → all checks PASS.
- [ ] Pre-build the dashboard once: `make dashboard` (`cd ui/dashboard && bun install && bun run dev`), leave it on `127.0.0.1:5173`.
- [ ] Start the live server in a spare pane: `make serve` (`copilot serve` on `127.0.0.1:8765`) — used in Segment 4.
- [ ] Delete stale run dirs so the CLI writes fresh: `rm -rf runs/spl-lint-demo runs/appinspect-demo runs/onboarding-demo`.
- [ ] Three surfaces: a terminal, the browser (dashboard tab, zoomed so the 5 metric cards and panels all fit), and the live-server pane. Optional 4th cutaway: VS Code with the repo open.

---

## Segment 1 — The problem (0:00–0:18)

| | |
|---|---|
| **Screen** | Title card, then the messy `fixtures/onboarding/sample_upi.log` scrolling — raw UPI lines, mixed timestamps, `payer_vpa`, `gstin`. |
| **Voiceover** | "Getting a Splunk app to production is expert-gated toil: hand-written extraction, AppInspect ping-pong, cost-tuning every search. Splunk's own AI can *explain* these failures — but nothing closes the loop, validates the fix, or remembers why." |
| **Cut on** | "…remembers why." Hard cut to terminal. |

---

## Segment 2 — The agent, live in the terminal (0:18–1:15)

Run all three loops back to back. They share one engine; only the artifact differs.

| | |
|---|---|
| **Command 1** | `copilot lint fixtures/spl_lint/costly_search.spl --out runs/spl-lint-demo` |
| **Voiceover** | "A deliberately costly search. The agent finds three cost anti-patterns — `index=*`, no time bound, an unbounded sort — diagnoses each, and rewrites it deterministically. Clean." |
| **Emphasize** | The healed query line: `earliest=-24h index=main … \| sort 1000 …`. `3 → 0`. |
| **Command 2** | `copilot appinspect fixtures/appinspect/broken_app --out runs/appinspect-demo` |
| **Voiceover** | "Now a broken app. AppInspect finds three real failures — a forbidden `local/`, a `user-seed.conf`, a forwarding `outputs.conf`. The agent patches each with a deterministic function — the LLM never touches the bytes — and re-runs AppInspect until green." |
| **Emphasize** | `Status: clean`, `Initial failures 3 → Final failures 0`. |
| **Command 3** | `copilot onboard fixtures/onboarding/sample_upi.log --out runs/onboarding-demo` |
| **Voiceover** | "And the live one. The agent ingests 150 raw events over HEC, then validates its field extraction against *real indexed events* — through the Splunk MCP server's `splunk_run_query` tool. Three gaps on the first candidate; one deterministic patch; re-validated through MCP — clean." |
| **Emphasize** | Say **"MCP server"** out loud. Point at `Ingested events: 150`, `3 → 0`, and the `Splunk source` line. This is the bonus-prize signal — give it the most terminal time. |
| **Cut on** | The "What to look at next" panel pointing to the dashboard. |

---

## Segment 3 — The dashboard: one engine, three loops (1:15–2:15)

| | |
|---|---|
| **Screen** | Browser → dashboard, **Lifecycle** overview (lands here by default). |
| **Voiceover (overview)** | "The same self-heal engine drove all three loops. Three clean runs, side by side — nine failures healed, real MCP calls counted." |
| **Cut to** | **Onboarding** stage. |
| **Voiceover** | "Onboarding, visualized: the MCP tool-call count, six CIM fields mapped — including `vpa → dest` — and `payer_vpa` and `payer_mobile` flagged as PII. Verified against live events, not guessed." |
| **Emphasize** | The **MCP tool calls** metric and the **CIM Mapping & PII** panel (PII chips). |
| **Cut to** | **AppInspect** stage. |
| **Voiceover** | "AppInspect: three iteration cards, Detect → Diagnose → Patch → Revalidate, red to green." |
| **Emphasize** | Let the **Self-Heal Timeline** and `3 → 0` land. |
| **Cut to** | **SPL Lint** stage, then the **Provenance Ledger** panel. |
| **Voiceover** | "And every fix — across every loop — is recorded: the failure, diagnosis, patch, rationale, validation result, timestamped. The next engineer isn't lost. Splunk explains; this remembers." |
| **Emphasize** | Scroll the Provenance Ledger; point to one diagnosis + rationale row with its changed-path chip. |

---

## Segment 4 — Live mode (2:15–2:40)

| | |
|---|---|
| **Screen** | Dashboard on the **SPL Lint** stage. Click **Go Live**. |
| **Voiceover** | "That was replay. This is live — the dashboard streaming a self-heal loop over SSE as it actually runs. Same engine, same render, real time." |
| **Emphasize** | The pulsing **Live** pill; the timeline filling in iteration by iteration to **Clean**. (Server: `make serve`, already running.) |

---

## Segment 5 — Close (2:40–2:58)

| | |
|---|---|
| **Screen** | Optional VS Code cutaway: **Terminal → Run Task → "Copilot: SPL lint self-heal"** (same `copilot` entry point from the IDE, via committed `.vscode/tasks.json`), then repo URL / title card. |
| **Voiceover** | "Three lifecycle stages on one engine, the Splunk MCP server orchestrating real actions, and an audit trail for every fix. Splunk explains. We resolve, validate, and remember." |
| **End on** | Repo URL on screen: `github.com/ik-labs/splunk-app-lifecycle-copilot`. |

---

## Timing budget

| Segment | Window | Budget |
|---|---|---|
| 1 Problem | 0:00–0:18 | 18s |
| 2 Terminal — three loops | 0:18–1:15 | 57s |
| 3 Dashboard — overview + stages + provenance | 1:15–2:15 | 60s |
| 4 Live mode | 2:15–2:40 | 25s |
| 5 Close | 2:40–2:58 | 18s |

## Recording tips

- The live `copilot onboard` run takes a few seconds (HEC ingest + index settle + MCP queries). Record it live once and trim dead air — do **not** fake it; the realness is the point. `lint` is instant and `appinspect` ~10s, so the terminal segment paces well.
- If the live MCP call is risky on the day, the dashboard replays all three loops from committed JSON with zero dependencies — record that as the safety net. Live mode (Segment 4) also runs only the static loops, so it never needs Splunk.
- Keep the **MCP tool-call** metric and the `splunk_run_query` mentions prominent; that's the explicit bonus-prize signal.
- Name Splunk's own AppInspect AI explicitly and position above it ("explains" vs "resolves / validates / remembers") — judges reward honest, sharp scoping. Stages 3 & 5 remain labeled roadmap.
