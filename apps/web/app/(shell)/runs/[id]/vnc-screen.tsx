"use client";

import { mintStreamTicket, takeOverRun } from "@step-by-step/api-client";
import { useEffect, useRef } from "react";

import { vncSocketUrl } from "./pane";

/**
 * The Worker's browser, streamed over the backend VNC pipe. View-only is
 * also set on the client so a second tab of the holding session cannot
 * type — the proxy authenticates that session with the control password.
 */

export function VncScreen({
  runId,
  interactive,
  enabled,
}: {
  runId: string;
  interactive: boolean;
  enabled: boolean;
}) {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const target = host.current;
    if (!enabled || target === null) {
      return;
    }
    let cancelled = false;
    let session: { disconnect: () => void } | null = null;

    const connect = async () => {
      const minted = interactive
        ? await takeOverRun({ path: { run_id: runId } })
        : await mintStreamTicket({ path: { run_id: runId } });
      if (cancelled || minted.error || minted.data === undefined) {
        return;
      }
      const { default: RFB } = await import("@novnc/novnc");
      if (cancelled) {
        return;
      }
      const rfb = new RFB(target, vncSocketUrl(minted.data.ws_url, window.location), {
        shared: true,
      });
      rfb.viewOnly = !interactive;
      rfb.scaleViewport = true;
      rfb.focusOnClick = interactive;
      rfb.background = "transparent";
      session = rfb;
    };

    void connect();
    return () => {
      cancelled = true;
      session?.disconnect();
      target.replaceChildren();
    };
  }, [runId, interactive, enabled]);

  return <div ref={host} className="h-full min-h-64 w-full bg-muted" />;
}
