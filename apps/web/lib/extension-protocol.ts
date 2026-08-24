/**
 * The names the app and the extension say to each other on the connect page,
 * and the reading of what arrives.
 *
 * The extension opens this channel rather than the app, because
 * `externally_connectable` cannot name an arbitrary self-hosted origin. So the
 * app never addresses the extension: it posts into its own window, where the
 * extension's injected bridge is listening, and answers what the bridge says.
 *
 * These names are the extension's — `apps/extension/src/lib/handshake.js` —
 * and `extension-protocol.test.ts` reads that file to keep the two the same.
 * A rename on one side that misses the other would break connecting with
 * nothing to show for it.
 */

/** The name on every message of this protocol, so a page's own bus is not ours. */
export const EXTENSION_CHANNEL = "step-by-step";

/** The app proving to the extension that this is the instance it asked for. */
export const HANDSHAKE = "connect-handshake";

/** The page asking the connected extension to announce itself. */
export const EXTENSION_PROBE = "connection-probe";

/** The extension's bridge saying it is in the page and listening. */
export const EXTENSION_READY = "extension-ready";

/** The extension saying the connection is made, and what version made it. */
export const CONNECT_ACCEPTED = "connect-accepted";

/** What the extension announces on the connect page. */
export type ExtensionMessage = {
  type: typeof EXTENSION_READY | typeof CONNECT_ACCEPTED;
  version: string;
};

/**
 * The extension's message inside whatever arrived, or `null`.
 *
 * Only the payload is read here. Whether it came from this window at this
 * origin is the caller's check, because only the caller has a window.
 */
export function readExtensionMessage(data: unknown): ExtensionMessage | null {
  if (typeof data !== "object" || data === null) {
    return null;
  }
  const message = data as Record<string, unknown>;
  if (message.channel !== EXTENSION_CHANNEL) {
    return null;
  }
  if (message.type !== EXTENSION_READY && message.type !== CONNECT_ACCEPTED) {
    return null;
  }
  return {
    type: message.type,
    version: typeof message.version === "string" ? message.version : "",
  };
}

/** The handshake this page hands over: the nonce the extension put in the URL. */
export function handshakeMessage(nonce: string, instanceOrigin: string) {
  return {
    channel: EXTENSION_CHANNEL,
    type: HANDSHAKE,
    nonce,
    instanceOrigin,
  } as const;
}
