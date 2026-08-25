"use client";

import { streamRunEvents } from "@step-by-step/api-client";
import { useEffect, useRef } from "react";

import type { RunEvent } from "./events";
import { isTerminal } from "./presentation";

import type { RunStatus } from "@step-by-step/api-client";

/**
 * Follow a live Run over SSE. Reconnection replays nothing: the caller
 * refetches over REST, then this hook subscribes from now on.
 */

export function useRunStream(
  runId: string | undefined,
  status: RunStatus | undefined,
  onEvent: (event: RunEvent) => void,
  onReconnect: () => Promise<void>,
): void {
  const eventRef = useRef(onEvent);
  const reconnectRef = useRef(onReconnect);
  eventRef.current = onEvent;
  reconnectRef.current = onReconnect;

  const live = status !== undefined && !isTerminal(status);

  useEffect(() => {
    if (runId === undefined || !live) {
      return;
    }
    const abort = new AbortController();
    let stopped = false;

    const listen = async () => {
      while (!stopped && !abort.signal.aborted) {
        try {
          const { stream } = await streamRunEvents({
            path: { run_id: runId },
            signal: abort.signal,
            sseMaxRetryAttempts: 0,
            onSseEvent: (frame) => {
              if (typeof frame.event === "string") {
                eventRef.current({
                  type: frame.event,
                  data:
                    typeof frame.data === "object" && frame.data !== null
                      ? (frame.data as Record<string, unknown>)
                      : {},
                });
              }
            },
          });
          for await (const _ of stream) {
            if (abort.signal.aborted) {
              break;
            }
          }
        } catch {
          // The socket dropped. Refetch, then subscribe from now on.
        }
        if (stopped || abort.signal.aborted) {
          break;
        }
        await reconnectRef.current();
        await new Promise((resolve) => {
          window.setTimeout(resolve, 1000);
        });
      }
    };

    void listen();
    return () => {
      stopped = true;
      abort.abort();
    };
  }, [runId, live]);
}
