# Demo Shot-List — Splunk App Lifecycle Copilot

Target length: **2:55** (hard cap 3:00). Judges may score on the video alone, so
record a clean backup take. Every time the agent calls the MCP server, keep it
on screen — the bonus prize rewards visible MCP orchestration.

Thesis line to land: **"Splunk's AI explains failures. This resolves, validates,
and remembers them."**

---

## Pre-roll setup (not recorded)

Do all of this before hitting record, so the live segment can't stall:

- [ ] `docker compose up -d` and wait for **healthy** (`docker inspect -f '{{.State.Health.Status}}' splunk-copilot`). First boot is ~1–2 min.
- [ ] `.venv/bin/python smoke_test.py` → all 4 checks PASS (run with the venv active so `splunk-appinspect` is on PATH).
- [ ] Confirm `.env` has a fresh `SPLUNK_MCP_ENCRYPTED_TOKEN` (token mint: `GET /services/mcp_token?username=admin&expires_on=%2B30d`).
- [ ] Pre-build the dashboard once: `cd ui/dashboard && bun install && bun run dev` (leave it running on `127.0.0.1:5173`).
- [ ] Delete stale run dirs so the CLI writes fresh: `rm -rf runs/onboarding-demo runs/appinspect-demo`.
- [ ] Terminal: large font, dark theme, window cropped to ~100 cols. Browser: dashboard tab ready, zoomed so the 5 metric cards and panels are all visible.
- [ ] Two surfaces only: a terminal and the browser. Optional 3rd cutaway: VS Code with the repo open.

---

## Segment 1 — The problem (0:00–0:20)

| | |
|---|---|
| **Screen** | Title card or the messy `fixtures/onboarding/sample_upi.log` scrolling — raw UPI lines, mixed timestamps, `payer_vpa`, `gstin`. |
| **Voiceover** | "Onboarding a new log source into Splunk is days of hand-written regex and CIM mapping. Then AppInspect ping-pong before you can ship. And when it's done, that knowledge lives in one engineer's head. Splunk's own AI can *explain* these failures — but nothing closes the loop, or remembers why." |
| **Cut on** | "…remembers why." Hard cut to terminal. |

---

## Segment 2 — Onboarding loop, live through MCP (0:20–1:05)

| | |
|---|---|
| **Command** | `copilot onboard fixtures/onboarding/sample_upi.log --out runs/onboarding-demo` |
| **Screen** | Terminal runs live. Narrate the real steps as the summary table renders. |
| **Voiceover** | "The agent ingests 150 raw events over HEC, then validates its extraction against *real indexed events* — through the Splunk MCP server's `splunk_run_query` tool. First candidate: three gaps — a timestamp format it misses, an unmapped CIM field, and unflagged PII. It diagnoses, applies one deterministic patch, and re-validates through MCP — clean." |
| **Emphasize** | Point at `Status: clean`, `Ingested events: 150`, `Initial failures 3 → Final failures 0`. Say the words "MCP server" out loud here. |
| **Cut to** | Browser → dashboard, **Onboarding** stage selected. Press **Restart** to replay. |
| **Voiceover (dashboard)** | "Same run, visualized. Watch the MCP tool-call count climb as it queries Splunk. Six CIM fields mapped — including `vpa → dest` — and `payer_vpa` and `payer_mobile` flagged as PII. This isn't a suggestion. It's verified against live events." |
| **Emphasize** | The **MCP tool calls** metric and the **CIM Mapping & PII** panel (PII chips visible). |

---

## Segment 3 — AppInspect loop, the hero shot (1:05–2:00)

| | |
|---|---|
| **Command** | `copilot appinspect fixtures/appinspect/broken_app --out runs/appinspect-demo` |
| **Screen** | Terminal runs the real AppInspect self-heal loop. |
| **Voiceover** | "Now a deliberately broken app. AppInspect finds three real failures: a forbidden `local/` directory, a `user-seed.conf`, and a forwarding `outputs.conf`. The agent diagnoses each, a deterministic patch function fixes it — the LLM never touches the bytes — and it re-runs AppInspect after every fix. Red… to green. Autonomously." |
| **Cut to** | Dashboard → click the **AppInspect** stage in the sidebar. Press **Restart**. |
| **Emphasize** | The Self-Heal Timeline: three iteration cards going Detect → Diagnose → Patch → Revalidate (pass). Let the "3 → 0" metric land. This is the most visceral moment — give it the most screen time. |

---

## Segment 4 — Platform thesis + provenance (2:00–2:35)

| | |
|---|---|
| **Screen** | Dashboard Provenance Ledger panel, then a quick flash of `architecture_diagram.md`. |
| **Voiceover** | "Both loops ran on the *same* self-heal engine — that reuse is the platform. And every fix is recorded: the failure, the diagnosis, the patch, the rationale, the validation result, timestamped. The next engineer isn't lost — the institutional memory is right here." |
| **Emphasize** | Scroll the ledger; point to one rationale line. Flash the architecture diagram showing stages 3–5 as the roadmap. |

---

## Segment 5 — Close (2:35–2:55)

| | |
|---|---|
| **Screen** | Optional VS Code cutaway: **Terminal → Run Task → "Copilot: SPL lint self-heal"** (same `copilot` entry point from the IDE, via the committed `.vscode/tasks.json`), then repo URL / title card. |
| **Voiceover** | "A week of expert-gated toil, compressed to an afternoon — with an audit trail, and the Splunk MCP server orchestrating real actions across the lifecycle. Splunk explains. We resolve, validate, and remember." |
| **End on** | Repo URL on screen. |

---

## Timing budget

| Segment | Window | Budget |
|---|---|---|
| 1 Problem | 0:00–0:20 | 20s |
| 2 Onboarding (MCP) | 0:20–1:05 | 45s |
| 3 AppInspect (hero) | 1:05–2:00 | 55s |
| 4 Thesis + provenance | 2:00–2:35 | 35s |
| 5 Close | 2:35–2:55 | 20s |

## Recording tips

- The live `copilot onboard` run takes a few seconds (HEC ingest + index settle + two MCP queries). If you want a tighter cut, record it live once, then trim dead air — do **not** fake it; the realness is the point.
- If the live MCP call is risky on the day, the dashboard replays both loops from committed JSON with zero dependencies — record that as the safety net.
- Keep the MCP tool-call metric and the `splunk_run_query` mentions prominent; that's the explicit bonus-prize signal.
- Name Splunk's own AppInspect AI explicitly and position above it ("explains" vs "resolves/validates/remembers") — judges reward honest, sharp scoping.
