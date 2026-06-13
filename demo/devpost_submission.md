# Devpost Submission — Splunk App Lifecycle Copilot

Copy-paste-ready text for the Devpost form. Fill the repo/video URLs where noted.

---

## Tagline (one line)

Splunk's AI explains failures. This copilot **resolves, validates, and remembers** them — self-healing loops that carry a Splunk app from raw logs to AppInspect-green to cost-clean SPL, with an auditable provenance trail.

## Elevator pitch (≈ 2 sentences)

The App Lifecycle Copilot runs closed self-heal loops — diagnose → deterministically patch → re-validate → repeat — across three stages of the Splunk app lifecycle, validating its work against a real Splunk instance through the Splunk MCP server. Every decision is written to a provenance ledger, so the fix is not just made but reviewable and remembered.

---

## Inspiration

Splunk's own AI (AppInspect AI Intelligence Reports, the AI Assistant) is excellent at **explaining** what's wrong — but a developer still has to do the resolving, re-validating, and remembering by hand. Onboarding a new data source, getting an app through AppInspect, and writing cost-aware SPL are exactly the expert-gated, repetitive tasks that eat an afternoon and leave no audit trail. We wanted to close that loop: an agent that doesn't just describe the failure, but fixes it, proves the fix against real Splunk, and records why.

## What it does

One shared self-heal engine drives **three working loops**:

1. **Onboarding (live MCP):** ingests a raw UPI/GST-style log sample through HEC, then validates inline `rex`/`eval` field-extraction candidates against the **real indexed events** via the Splunk MCP server's `splunk_run_query`. It diagnoses coverage gaps, CIM-mapping gaps, and PII, switches to a more robust candidate, and re-validates until the extraction is CIM-clean — six CIM mappings and two PII flags on the demo fixture.
2. **AppInspect:** runs `splunk-appinspect` as local static analysis on a deliberately broken app, parses the JSON failures, applies deterministic patch functions, and re-runs until zero failures. No live Splunk required.
3. **Cost-aware SPL lint:** lints a deliberately costly search for cost anti-patterns (`index=*`, no time bound, unbounded `| sort`) and applies deterministic rewrites (`index=main`, `earliest=-24h`, `| sort 1000`) until the query is clean. No live Splunk required.

Every patch across every loop is appended to a **provenance ledger** — `{stage, iteration, failure, diagnosis, patch, rationale, validation_result, timestamp, changed_paths}` — the "and remember" half of the thesis.

A **React dashboard** replays all three loops from committed events (no Splunk needed), opening on a Lifecycle overview and drilling into each stage's timeline, metrics, CIM/PII panel, and a full provenance audit-trail panel. It also has a **Live mode**: a "Go Live" button streams a loop's events over Server-Sent Events as it actually runs, rendered through the same reducer as replay. The same `copilot` agent is wired into **VS Code** as Run Task / Run-and-Debug entry points.

## How we built it

- **Python** package `lifecycle_copilot` (CLI `copilot`): a single artifact-agnostic `SelfHealEngine` (`diagnose → select deterministic patch → apply → re-validate`, iteration-capped) reused verbatim by all three loops — only the diagnosis source and patch registry differ. The LLM produces diagnosis and rationale **text only**; concrete file changes are made by deterministic patch functions from a constrained registry, which keeps the demo repeatable and the audit trail defensible.
- **Splunk MCP server** as the action surface for onboarding: an encrypted-token-authenticated streamable-HTTP client calling `splunk_run_query` to validate extractions against real events. HEC for ingestion; `splunklib` SDK where simpler than MCP.
- **`splunk-appinspect`** CLI for the AppInspect loop; a small deterministic SPL cost ruleset for the lint loop.
- **Dashboard:** React + TypeScript + Vite + Bun; a pure event-stream reducer (unit-tested) renders both replay and live identically. Live transport is a Starlette + SSE server that runs a static loop in a background thread and streams each emitted event.
- **Splunk Enterprise** in Docker (`splunk/splunk:latest`) with HEC enabled for the live onboarding slice.

## Best Use of Splunk MCP Server

The onboarding loop is built around the MCP server doing **meaningful, repeated, real work** — not a single call. `splunk_run_query` is the validation oracle the self-heal loop iterates against: each candidate extraction is run against real indexed events, the loop reads the actual extracted fields back, diagnoses the gap, patches, and re-queries through MCP until convergence. The agent uses the encrypted MCP token (not a plain REST bearer token), and the loop hard-fails if the MCP server or `splunk_run_query` is unavailable — the integration is load-bearing, not decorative.

## Challenges we ran into

- **Indexing race:** HEC acknowledges before indexing completes, so the first MCP validation could see zero events and mis-diagnose. We added a bounded settle step that polls `| stats count` through MCP until the indexed count matches what was ingested — making runs deterministic.
- **One patch, many gaps:** the onboarding candidate swap heals timestamp, CIM, and PII gaps at once, but only the selected gap emits per-failure events. The dashboard reducer backfills the other gaps on a clean completion so the timeline reads as fully healed.
- **Encrypted MCP token:** the MCP token is RSA-encrypted by the Splunk MCP Server app, not a REST bearer token — minting and wiring it correctly (including a relative-expiry quirk) took care.
- **Keeping it honest:** we deliberately constrained the LLM to text and kept patches deterministic, so judges can trust the audit trail and reproduce every run.

## Accomplishments we're proud of

- **One engine, three loops** — adding the SPL lint loop reused the self-heal engine verbatim, which is the platform thesis made concrete.
- A live, end-to-end **MCP-validated** onboarding run: 150 events ingested, three gaps healed, six CIM mappings, two PII flags, real `splunk_run_query` calls.
- A dashboard that runs in **both replay and live** mode off the same reducer, fully responsive, with a real provenance audit trail.
- Deterministic, reproducible loops with a green test suite (Python + dashboard).

## What we learned

The leverage is in the **closed loop plus provenance**, not in a bigger model. Constraining the agent to diagnosis text and deterministic patches gave us repeatability and a defensible audit trail — and made the "one engine, many loops" platform story credible rather than aspirational.

## What's next

Stages 3 (scaffold + test data) and 5 (Simple XML → Dashboard Studio migration) on the same engine; `splunk_get_knowledge_objects` to reconcile against existing field extractions and data models; emitting final `props.conf`/`transforms.conf` from the onboarding loop; and surfacing the provenance ledger back into Splunk as an index.

## Built with

`python` · `splunk` · `splunk-mcp-server` · `splunk-appinspect` · `splunklib` · `hec` · `cim` · `spl` · `starlette` · `server-sent-events` · `react` · `typescript` · `vite` · `bun` · `docker` · `vscode`

---

## Form logistics

- **Track:** Platform & Developer Experience
- **Bonus:** Best Use of Splunk MCP Server
- **Newly created in the submission window:** Yes — the entire project (code, fixtures, dashboard, docs) was created within the hackathon window; commit history is public on the repo.
- **Repository:** https://github.com/ik-labs/splunk-app-lifecycle-copilot  (public; MIT license shows in the GitHub About)
- **Demo video (<3 min):** `<PUBLIC_VIDEO_URL>`  (script: `demo/demo_script.md`)
- **Architecture diagram:** `architecture_diagram.md` in the repo
