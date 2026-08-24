/** The postMessage protocol shared by the app and its connected extension. */

import type { Variable } from "@step-by-step/api-client";

export const EXTENSION_CHANNEL = "step-by-step";
export const HANDSHAKE = "connect-handshake";
export const EXTENSION_PROBE = "connection-probe";
export const EXTENSION_READY = "extension-ready";
export const CONNECT_ACCEPTED = "connect-accepted";
export const RECORDING_PENDING = "recording-pending";
export const RECORDING_PENDING_ACCEPTED = "recording-pending-accepted";
export const RECORDING_TOKEN_EXPIRED = "recording-token-expired";
export const RECORDING_TOKEN = "recording-token";
export const RECORDING_FINISHED = "recording-finished";

export type ExtensionMessage = {
  type:
    | typeof EXTENSION_READY
    | typeof CONNECT_ACCEPTED
    | typeof RECORDING_PENDING_ACCEPTED
    | typeof RECORDING_TOKEN_EXPIRED
    | typeof RECORDING_FINISHED;
  version: string;
  sessionId?: string;
};

export function readExtensionMessage(data: unknown): ExtensionMessage | null {
  if (typeof data !== "object" || data === null) return null;
  const message = data as Record<string, unknown>;
  if (message.channel !== EXTENSION_CHANNEL) return null;
  const type = message.type;
  if (type === EXTENSION_READY || type === CONNECT_ACCEPTED) {
    return { type, version: typeof message.version === "string" ? message.version : "" };
  }
  if (
    (type === RECORDING_PENDING_ACCEPTED ||
      type === RECORDING_TOKEN_EXPIRED ||
      type === RECORDING_FINISHED) &&
    typeof message.sessionId === "string"
  ) {
    return {
      type,
      version: typeof message.version === "string" ? message.version : "",
      sessionId: message.sessionId,
    };
  }
  return null;
}

export function handshakeMessage(nonce: string, instanceOrigin: string) {
  return { channel: EXTENSION_CHANNEL, type: HANDSHAKE, nonce, instanceOrigin } as const;
}

export type PendingRecording = {
  sessionId: string;
  token: string;
  backendOrigin: string;
  workflowId: string;
  workflowName: string;
  variables: Variable[];
};

export function recordingPendingMessage(recording: PendingRecording) {
  return {
    channel: EXTENSION_CHANNEL,
    type: RECORDING_PENDING,
    ...recording,
    mode: "record" as const,
  };
}

export function recordingTokenMessage(sessionId: string, token: string) {
  return { channel: EXTENSION_CHANNEL, type: RECORDING_TOKEN, sessionId, token } as const;
}
