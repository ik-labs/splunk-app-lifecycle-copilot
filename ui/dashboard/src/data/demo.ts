import demoEvents from "../../../../demo/appinspect_events.json";
import demoProvenanceRaw from "../../../../demo/appinspect_provenance.jsonl?raw";

import { parseProvenance } from "../lib/replay";
import type { ProvenanceEntry, ReplayEvent } from "../types";

export const initialEvents = demoEvents as ReplayEvent[];
export const initialProvenance = parseProvenance(demoProvenanceRaw) as ProvenanceEntry[];

export const artifactRows = [
  {
    type: "Initial Report",
    path: "appinspect/iteration-00.json",
    status: "failed"
  },
  {
    type: "Validation Report",
    path: "appinspect/iteration-01.json",
    status: "patched"
  },
  {
    type: "Validation Report",
    path: "appinspect/iteration-02.json",
    status: "patched"
  },
  {
    type: "Final Report",
    path: "appinspect/iteration-03.json",
    status: "clean"
  },
  {
    type: "Replay Events",
    path: "events.json",
    status: "replay"
  },
  {
    type: "Provenance",
    path: "provenance.jsonl",
    status: "ledger"
  }
];
