import type { LoopName, ReplayEvent } from "../types";

const LIVE_BASE =
  (import.meta.env.VITE_LIVE_URL as string | undefined) ?? "http://127.0.0.1:8765";

// Loops that the live server can run on demand (static, no Splunk required).
export const LIVE_LOOPS: LoopName[] = ["appinspect", "spl_lint"];

export function isLiveLoop(loop: LoopName): boolean {
  return LIVE_LOOPS.includes(loop);
}

export interface LiveStreamHandlers {
  onEvent: (event: ReplayEvent) => void;
  onDone: () => void;
  onError: () => void;
}

/** Open an SSE connection to the live self-heal stream. Returns a cancel fn. */
export function startLiveStream(loop: LoopName, handlers: LiveStreamHandlers): () => void {
  const url = `${LIVE_BASE}/api/stream?loop=${encodeURIComponent(loop)}`;
  const source = new EventSource(url);
  let closed = false;

  const close = () => {
    if (!closed) {
      closed = true;
      source.close();
    }
  };

  source.addEventListener("loop_event", (event) => {
    try {
      handlers.onEvent(JSON.parse((event as MessageEvent).data) as ReplayEvent);
    } catch {
      // Ignore malformed frames; the stream keeps going.
    }
  });

  source.addEventListener("loop_done", () => {
    close();
    handlers.onDone();
  });

  source.onerror = () => {
    // EventSource auto-reconnects on transport errors; we treat any error as
    // terminal so a missing server surfaces immediately instead of looping.
    if (!closed) {
      close();
      handlers.onError();
    }
  };

  return close;
}
