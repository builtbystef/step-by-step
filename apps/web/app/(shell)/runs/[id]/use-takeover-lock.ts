"use client";

import { useEffect, useState } from "react";

import { heldElsewhere, type TakeoverLock } from "./pane";

/**
 * Coordinates takeover across tabs of the same browser. The backend keys
 * control on the session cookie, which every tab shares, so a second tab
 * learns about the hold here and stays view-only.
 */

const CHANNEL = "takeover-hold";

function storageKey(runId: string): string {
  return `takeover-hold:${runId}`;
}

function readLock(runId: string): TakeoverLock | null {
  try {
    const raw = window.localStorage.getItem(storageKey(runId));
    if (raw === null) {
      return null;
    }
    const parsed = JSON.parse(raw) as TakeoverLock;
    return typeof parsed.tabId === "string" ? parsed : null;
  } catch {
    return null;
  }
}

function tabIdOf(): string {
  const existing = window.sessionStorage.getItem("takeover-tab-id");
  if (existing !== null) {
    return existing;
  }
  const minted = crypto.randomUUID();
  window.sessionStorage.setItem("takeover-tab-id", minted);
  return minted;
}

export function useTakeoverLock(runId: string): {
  tabId: string;
  heldElsewhere: boolean;
  claim: () => void;
  release: () => void;
} {
  const [tabId, setTabId] = useState("");
  const [lock, setLock] = useState<TakeoverLock | null>(null);

  useEffect(() => {
    const id = tabIdOf();
    setTabId(id);
    setLock(readLock(runId));

    const onStorage = (event: StorageEvent) => {
      if (event.key === storageKey(runId)) {
        setLock(readLock(runId));
      }
    };
    window.addEventListener("storage", onStorage);

    const channel = "BroadcastChannel" in window ? new BroadcastChannel(CHANNEL) : null;
    const onMessage = (event: MessageEvent<unknown>) => {
      if (event.data === runId) {
        setLock(readLock(runId));
      }
    };
    channel?.addEventListener("message", onMessage);

    return () => {
      window.removeEventListener("storage", onStorage);
      channel?.removeEventListener("message", onMessage);
      channel?.close();
    };
  }, [runId]);

  const publish = () => {
    if ("BroadcastChannel" in window) {
      const channel = new BroadcastChannel(CHANNEL);
      channel.postMessage(runId);
      channel.close();
    }
  };

  return {
    tabId,
    heldElsewhere: tabId !== "" && heldElsewhere(lock, tabId),
    claim: () => {
      if (tabId === "") {
        return;
      }
      const next: TakeoverLock = { tabId, at: new Date().toISOString() };
      window.localStorage.setItem(storageKey(runId), JSON.stringify(next));
      setLock(next);
      publish();
    },
    release: () => {
      const current = readLock(runId);
      if (current === null || current.tabId !== tabId) {
        return;
      }
      window.localStorage.removeItem(storageKey(runId));
      setLock(null);
      publish();
    },
  };
}
