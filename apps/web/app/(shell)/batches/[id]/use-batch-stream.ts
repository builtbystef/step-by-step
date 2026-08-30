"use client";

import { streamBatchEvents } from "@step-by-step/api-client";
import { useEffect, useRef } from "react";

import type { BatchEvent } from "./events";

export function useBatchStream(
  batchId: string | undefined,
  live: boolean,
  onEvent: (event: BatchEvent) => void,
  onReconnect: () => Promise<void>,
): void {
  const eventRef = useRef(onEvent);
  const reconnectRef = useRef(onReconnect);
  eventRef.current = onEvent;
  reconnectRef.current = onReconnect;

  useEffect(() => {
    if (batchId === undefined || !live) {
      return;
    }
    const abort = new AbortController();
    let stopped = false;

    const listen = async () => {
      while (!stopped && !abort.signal.aborted) {
        try {
          const { stream } = await streamBatchEvents({
            path: { batch_id: batchId },
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
        } catch {}
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
  }, [batchId, live]);
}
