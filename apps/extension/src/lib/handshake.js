export const CHANNEL = "step-by-step";

export const HANDSHAKE = "connect-handshake";

export const PROBE = "connection-probe";

export const READY = "extension-ready";

export const ACCEPTED = "connect-accepted";

export const RECORDING_PENDING = "recording-pending";

export const RECORDING_PENDING_ACCEPTED = "recording-pending-accepted";

export const RECORDING_STATUS = "recording-status";

export const RECORDING_TOKEN_EXPIRED = "recording-token-expired";

export const RECORDING_TOKEN = "recording-token";

export const RECORDING_FINISHED = "recording-finished";

export const REPICK_CANDIDATES = "repick-candidates";

const NONCE_BYTES = 32;

export function mintNonce() {
  const bytes = crypto.getRandomValues(new Uint8Array(NONCE_BYTES));
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function readHandshake(data) {
  if (typeof data !== "object" || data === null) {
    return null;
  }
  const { channel, type, nonce, instanceOrigin } = data;
  if (channel !== CHANNEL || type !== HANDSHAKE) {
    return null;
  }
  if (typeof nonce !== "string" || typeof instanceOrigin !== "string") {
    return null;
  }
  return { nonce, instanceOrigin };
}

export function isProtocolMessage(data) {
  return typeof data === "object" && data !== null && data.channel === CHANNEL;
}

export function judgeHandshake({ message, sender, attempt, extensionId }) {
  if (!attempt) {
    return refuse("no-attempt");
  }
  if (!sender || sender.id !== extensionId) {
    return refuse("not-our-sender");
  }
  if (!sender.tab) {
    return refuse("not-a-tab");
  }
  if (sender.frameId !== 0) {
    return refuse("not-the-top-frame");
  }
  if (sender.tab.id !== attempt.tabId) {
    return refuse("not-the-connected-tab");
  }
  if (sender.origin !== attempt.origin) {
    return refuse("wrong-origin");
  }

  const handshake = readHandshake(message);
  if (handshake === null) {
    return refuse("malformed");
  }
  if (handshake.instanceOrigin !== sender.origin) {
    return refuse("wrong-origin");
  }
  if (handshake.nonce !== attempt.nonce) {
    return refuse("wrong-nonce");
  }
  return { accepted: true, origin: attempt.origin };
}

function refuse(reason) {
  return { accepted: false, reason };
}
