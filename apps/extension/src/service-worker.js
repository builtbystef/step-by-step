/**
 * The extension's coordinator: it holds the connection to one instance, and it
 * is the only thing here that decides anything.
 *
 * Restartable by design. Chrome stops this worker after 30 seconds of idle
 * and starts it again on the next event, so nothing is kept in a variable that
 * has to survive: the connection lives in `storage.local` and the connect
 * attempt in `storage.session`, and every listener is registered at the top
 * level, where a restart re-registers it.
 *
 * The connect flow, once per instance:
 *
 *   the popup asks Chrome for the origin the user typed, from their click
 *   -> this worker opens the app's connect page there and injects the bridge
 *   -> the page hands over the nonce this worker minted for the attempt
 *   -> the origin is remembered as connected
 *
 * The fallback, when that does not happen: the app shows a one-time connect
 * code, the user pastes it into the popup, and this worker spends it at the
 * instance. Either way the one granted origin is what the bridge is injected
 * into and what this worker may fetch.
 */

import {
  ACCEPTED,
  CHANNEL,
  HANDSHAKE,
  READY,
  isProtocolMessage,
  judgeHandshake,
  mintNonce,
} from "./lib/handshake.js";
import { originPattern, readInstanceUrl } from "./lib/instance.js";
import { pageBridge } from "./lib/page-bridge.js";

/** The connected instance, in `storage.local`: it outlives the browser. */
const CONNECTION_KEY = "connection";

/** The connect attempt in flight, in `storage.session`: it must not. */
const ATTEMPT_KEY = "connect-attempt";

/** The app's page that hands over the handshake. */
const CONNECT_PATH = "/connect";

/** Where a connect code is spent. */
const CONNECT_ENDPOINT = "/api/extension/connect";

/**
 * How long an attempt stays open.
 *
 * Long enough to sign in on the way to the connect page, short enough that a
 * tab left open for an afternoon is not still a handshake waiting to be made.
 */
const ATTEMPT_LIFETIME_MS = 5 * 60 * 1000;

/** The longest connect code this worker will carry to an instance. */
const CODE_LENGTH_LIMIT = 64;

const VERSION = chrome.runtime.getManifest().version;

const BRIDGE_PROTOCOL = {
  channel: CHANNEL,
  handshake: HANDSHAKE,
  ready: READY,
  accepted: ACCEPTED,
  version: VERSION,
};

chrome.runtime.onMessage.addListener((message, sender, respond) => {
  answer(message, sender).then(respond, (failure) => {
    console.warn("step-by-step: a message could not be answered", failure);
    respond({ error: "failed" });
  });
  // The answer is a promise, and Chrome closes the channel on a synchronous
  // return unless it is told to wait.
  return true;
});

chrome.tabs.onUpdated.addListener((tabId, change) => {
  if (change.status === "complete") {
    void injectIntoTheConnectPage(tabId);
  }
});

/**
 * What was said, and then whether the sayer may say it.
 *
 * A page may say exactly one thing — the handshake — and everything else is a
 * command from one of this extension's own surfaces. A page that tries a
 * command is answered with nothing, rather than with a refusal it could learn
 * from; and nothing a page could send passes the handshake's own judgement,
 * because an extension page's origin is never the attempt's.
 */
async function answer(message, sender) {
  if (isProtocolMessage(message)) {
    return acceptHandshake(message, sender);
  }
  if (!fromOurOwnSurfaces(sender)) {
    return { ignored: true };
  }
  switch (message?.type) {
    case "connection":
      return { connection: await connection(), version: VERSION };
    case "connect-through-the-page":
      return openTheConnectPage(message.origin);
    case "connect-with-code":
      return spendConnectCode(message.origin, message.code);
    case "disconnect":
      return disconnect();
    default:
      return { ignored: true };
  }
}

/**
 * The second gate: a handshake the bridge forwarded, held to the attempt.
 *
 * The tab is answered with whether it was accepted and never with why. The
 * reason is for whoever is reading this worker's log — a page that guessed
 * wrong learns only that it guessed.
 */
async function acceptHandshake(message, sender) {
  const verdict = judgeHandshake({
    message,
    sender,
    attempt: await attempt(),
    extensionId: chrome.runtime.id,
  });
  if (!verdict.accepted) {
    console.warn(`step-by-step: refused a handshake (${verdict.reason})`);
    return { accepted: false };
  }
  await remember(verdict.origin);
  await chrome.storage.session.remove(ATTEMPT_KEY);
  return { accepted: true, version: VERSION };
}

/** Open the app's connect page for a fresh attempt, and wait to be told. */
async function openTheConnectPage(origin) {
  const asked = canonical(origin);
  if (asked === null) {
    return { opened: false, reason: "not-an-instance" };
  }
  if (!(await permitted(asked))) {
    return { opened: false, reason: "not-permitted" };
  }

  const nonce = mintNonce();
  const tab = await chrome.tabs.create({
    url: `${asked}${CONNECT_PATH}?nonce=${encodeURIComponent(nonce)}`,
  });
  await chrome.storage.session.set({
    [ATTEMPT_KEY]: { origin: asked, nonce, tabId: tab.id, openedAt: Date.now() },
  });

  // A page on the same machine can finish loading before that write lands, and
  // the load is what the bridge is injected on. So the tab is asked where it
  // got to rather than trusted to announce itself again: whichever of the two
  // happened, exactly one injection follows, and the bridge ignores a second.
  await injectIfLoaded(tab.id);
  return { opened: true };
}

/**
 * Spend a one-time connect code at the instance the user typed.
 *
 * What a 200 proves is what the handshake proves: the origin is a live
 * instance, and somebody signed into it authorized this pairing. The code is
 * the instance's to check — nothing here reads it beyond its length.
 */
async function spendConnectCode(origin, code) {
  const asked = canonical(origin);
  if (asked === null) {
    return { connected: false, reason: "not-an-instance" };
  }
  if (typeof code !== "string" || code.trim() === "" || code.length > CODE_LENGTH_LIMIT) {
    return { connected: false, reason: "bad-code" };
  }
  if (!(await permitted(asked))) {
    return { connected: false, reason: "not-permitted" };
  }

  let response;
  try {
    response = await fetch(`${asked}${CONNECT_ENDPOINT}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: code.trim() }),
    });
  } catch {
    return { connected: false, reason: "unreachable" };
  }
  if (!response.ok) {
    return { connected: false, reason: response.status === 401 ? "bad-code" : "unreachable" };
  }

  await remember(asked);
  await chrome.storage.session.remove(ATTEMPT_KEY);
  return { connected: true };
}

/**
 * Give up the instance, and the access to it along with the instance.
 *
 * Handing the permission back is the part that can fail — a build installed by
 * policy holds its origins as required permissions, and Chrome refuses to drop
 * one. The disconnection stands either way: what the extension will do is
 * decided by what it has stored, not by what it is still allowed to reach.
 */
async function disconnect() {
  const held = await connection();
  await chrome.storage.local.remove(CONNECTION_KEY);
  await chrome.storage.session.remove(ATTEMPT_KEY);
  if (held !== null) {
    try {
      await chrome.permissions.remove({ origins: [originPattern(held.origin)] });
    } catch (kept) {
      console.warn("step-by-step: the site access could not be given back", kept);
    }
  }
  return { connection: null, version: VERSION };
}

/** Inject now if the tab finished loading before the attempt was written. */
async function injectIfLoaded(tabId) {
  const tab = await chrome.tabs.get(tabId);
  if (tab.status === "complete") {
    await injectIntoTheConnectPage(tabId);
  }
}

/** Put the bridge into the tab this attempt opened, and into no other. */
async function injectIntoTheConnectPage(tabId) {
  const pending = await attempt();
  if (pending === null || pending.tabId !== tabId) {
    return;
  }
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      func: pageBridge,
      args: [BRIDGE_PROTOCOL],
    });
  } catch (refused) {
    console.warn("step-by-step: the connect page could not be reached", refused);
  }
}

async function connection() {
  const held = await chrome.storage.local.get(CONNECTION_KEY);
  return held[CONNECTION_KEY] ?? null;
}

async function remember(origin) {
  await chrome.storage.local.set({
    [CONNECTION_KEY]: { origin, connectedAt: new Date().toISOString() },
  });
}

/** The attempt in flight, or `null` — an expired one is not one. */
async function attempt() {
  const stored = await chrome.storage.session.get(ATTEMPT_KEY);
  const pending = stored[ATTEMPT_KEY] ?? null;
  if (pending === null) {
    return null;
  }
  if (Date.now() - pending.openedAt > ATTEMPT_LIFETIME_MS) {
    await chrome.storage.session.remove(ATTEMPT_KEY);
    return null;
  }
  return pending;
}

/**
 * Whether this came from a surface of the extension's own — the popup, or that
 * same page opened in a tab, which is how anyone looks at it while working.
 *
 * The extension's pages are not web-accessible resources, so no site can open
 * one: being at this extension's own address is the whole of the check.
 */
function fromOurOwnSurfaces(sender) {
  return (
    sender.id === chrome.runtime.id && (sender.url ?? "").startsWith(chrome.runtime.getURL(""))
  );
}

/**
 * The origin as this extension writes it, or `null`.
 *
 * The popup normalizes what was typed, so anything that arrives here spelled
 * differently was not typed by anybody.
 */
function canonical(origin) {
  if (typeof origin !== "string") {
    return null;
  }
  const read = readInstanceUrl(origin);
  return read.origin === origin ? origin : null;
}

/** Whether Chrome has actually granted the origin — the popup asks, this checks. */
function permitted(origin) {
  return chrome.permissions.contains({ origins: [originPattern(origin)] });
}
