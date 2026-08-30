import type { ConnectionState } from "./labels";
import { EXTENSION_CHANNEL, EXTENSION_PROBE, readExtensionMessage } from "./extension-protocol";

export const EXTENSION_PROBE_TIMEOUT_MS = 1_500;

export interface ProbeWindow extends EventTarget {
  readonly location: { readonly origin: string };
  postMessage(message: unknown, targetOrigin: string): void;
}

export function probeExtension(
  page: ProbeWindow,
  timeoutMs = EXTENSION_PROBE_TIMEOUT_MS,
): Promise<string | null> {
  return new Promise((resolve) => {
    let settled = false;

    const finish = (version: string | null) => {
      if (settled) return;
      settled = true;
      page.removeEventListener("message", onMessage);
      clearTimeout(timeout);
      resolve(version);
    };

    const onMessage = (received: Event) => {
      const event = received as MessageEvent;
      if (event.source !== page || event.origin !== page.location.origin) return;
      const message = readExtensionMessage(event.data);
      if (message === null || message.version === "") return;
      finish(message.version);
    };

    page.addEventListener("message", onMessage);
    const timeout = setTimeout(() => {
      finish(null);
    }, timeoutMs);
    page.postMessage({ channel: EXTENSION_CHANNEL, type: EXTENSION_PROBE }, page.location.origin);
  });
}

export function watchWindowFocus(page: EventTarget, probe: () => void): () => void {
  page.addEventListener("focus", probe);
  return () => {
    page.removeEventListener("focus", probe);
  };
}

function versionAtLeast(version: string, minimum: string): boolean {
  const actual = version.split(".").map(Number);
  const required = minimum.split(".").map(Number);
  const width = Math.max(actual.length, required.length);
  for (let index = 0; index < width; index += 1) {
    const left = actual[index] ?? 0;
    const right = required[index] ?? 0;
    if (left !== right) return left > right;
  }
  return true;
}

export function connectionState(version: string | null, minimumSupported: string): ConnectionState {
  if (version === null) return "not_connected";
  return versionAtLeast(version, minimumSupported) ? "connected" : "out_of_date";
}
