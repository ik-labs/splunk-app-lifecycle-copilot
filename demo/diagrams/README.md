# Rendered Architecture Diagrams

PNG exports of the project's Mermaid diagrams, for the demo video and the Devpost
gallery. Regenerate any of them with
[`@mermaid-js/mermaid-cli`](https://github.com/mermaid-js/mermaid-cli):

```bash
bunx @mermaid-js/mermaid-cli -i ../../architecture_diagram.md -o /tmp/out.png -b white -w 2400
bunx @mermaid-js/mermaid-cli -i ../architecture_demo.md       -o /tmp/out.png -b white -w 2400
```

| File | What it shows | Source |
|---|---|---|
| `0-architecture-diagram.png` | Required hackathon artifact — how the app interacts with Splunk, where AI sits, and the cross-service data flow. | [`architecture_diagram.md`](../../architecture_diagram.md) |
| `1-system-overview.png` | One engine, three loops; Splunk (HEC + MCP) feeds onboarding; dashboard replays/streams emitted events. | [`architecture_demo.md` §1](../architecture_demo.md) |
| `2-self-heal-engine.png` | The shared spine as a call sequence: `validate → diagnose (LLM text) → apply_patch (deterministic) → re-validate → ledger_entry`. | [`architecture_demo.md` §2](../architecture_demo.md) |
| `3-onboarding-live-mcp.png` | Live MCP path: 150 events → HEC → bounded index-settle → candidate swap → clean, validated by real `splunk_run_query` calls. | [`architecture_demo.md` §3](../architecture_demo.md) |
| `4-live-mode-sse.png` | "Go Live" runtime: worker thread runs the loop, `on_event` → `asyncio.Queue` → SSE → same reducer as replay. | [`architecture_demo.md` §4](../architecture_demo.md) |
| `5-module-map.png` | File-level layout of the Python package and the dashboard. | [`architecture_demo.md` §5](../architecture_demo.md) |

`0-…` is the diagram judges are required to find at the repo root; `1–5` are the
deeper, presentation-ready views used in the demo walkthrough.
