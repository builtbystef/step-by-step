/**
 * The connect handshake: what the app's connect page says, and the rule that
 * decides whether the extension believes it.
 *
 * `externally_connectable` cannot name an arbitrary self-hosted origin, so the
 * extension opens this channel rather than the app. That makes every message
 * here untrusted twice over: the page is one the user pointed us at, and any
 * tab may talk to the service worker. So an accepted handshake has to be all
 * three of the tab this attempt opened, the origin this attempt asked
 * permission for, and the nonce this attempt minted — none of which a page
 * that was not opened by this attempt can supply.
 *
 * Nothing in this module touches a `chrome` API, which is what lets the page
 * side, the worker side, and the tests all read the same rule.
 */

/** The name on every message of this protocol, so a page's own bus is not ours. */
export const CHANNEL = "step-by-step";

/** The app's connect page proving it is the instance the user asked for. */
export const HANDSHAKE = "connect-handshake";

/** The connected page asking the extension to announce itself and its version. */
export const PROBE = "connection-probe";

/** The extension telling a page it is there, so the page may hand the handshake over. */
export const READY = "extension-ready";

/** The extension telling the page the connection is made. */
export const ACCEPTED = "connect-accepted";

const NONCE_BYTES = 32;

/**
 * A fresh nonce for one connect attempt: 256 bits from the CSPRNG, in hex.
 *
 * Hex because it travels in a URL the page reads back, and a value that
 * survives copying is worth more here than eight fewer characters.
 */
export function mintNonce() {
  const bytes = crypto.getRandomValues(new Uint8Array(NONCE_BYTES));
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

/**
 * The handshake inside a message, or `null` for anything else.
 *
 * A page's `window` carries every library's own postMessage traffic, so the
 * shape check is the first gate rather than an assertion: not being a
 * handshake is ordinary, and only a message that claims to be one and is
 * malformed is worth refusing loudly.
 */
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

/**
 * Whether a message belongs to this protocol at all.
 *
 * It is what the service worker routes on: everything on this channel came
 * from a page and is judged below, and everything else is a command from one
 * of the extension's own surfaces. Routing on the message rather than on
 * whether the sender had a tab is what keeps an extension page open in a tab —
 * which is how anyone debugs the popup — from being read as a page.
 */
export function isProtocolMessage(data) {
  return typeof data === "object" && data !== null && data.channel === CHANNEL;
}

/**
 * Whether the service worker may act on a handshake a content script forwarded.
 *
 * The order is the order of cheapness and of consequence: who sent it, from
 * where, and only then what it says. A refusal names its reason so that the
 * popup can tell "nothing answered" from "something answered wrongly", and so
 * that a test can say which rule caught it.
 *
 * The nonce is compared with `===`. A timing-safe comparison would defend
 * against an attacker who can measure a reply that this code never sends: an
 * unaccepted handshake is answered with nothing at all.
 */
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
