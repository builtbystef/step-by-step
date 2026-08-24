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
 *   the popup says what it is about to do, then asks Chrome for the origin
 *   -> the grant arrives here, and the popup usually does not: Chrome's dialog
 *      takes focus, and a popup that loses focus is closed
 *   -> so this worker finishes what was announced, whoever is left to tell it:
 *      it opens the app's connect page and injects the bridge
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
  PROBE,
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

/** What the popup was about to do when it asked Chrome, also in the session. */
const INTENT_KEY = "connect-intent";

/**
 * The address last typed in the popup, in the session too.
 *
 * Chrome closes a popup the moment it loses focus, and a connect code has to be
 * fetched from the app — so the popup that comes back is a new one every time,
 * and without this the address would be typed once for every attempt. It is
 * kept for as long as the browser runs and no longer: it is what somebody is in
 * the middle of, not something this extension knows.
 */
const ADDRESS_KEY = "typed-address";

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

/**
 * How long an announced connect waits for Chrome's dialog to be answered.
 *
 * The dialog is a decision a person makes, so it is generous; and it is not
 * indefinite, so a dialog dismissed and forgotten does not turn a site access
 * granted by hand an hour later into a tab nobody asked for.
 */
const INTENT_LIFETIME_MS = 2 * 60 * 1000;

/** The longest connect code this worker will carry to an instance. */
const CODE_LENGTH_LIMIT = 64;

const VERSION = chrome.runtime.getManifest().version;

const BRIDGE_PROTOCOL = {
  channel: CHANNEL,
  handshake: HANDSHAKE,
  probe: PROBE,
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
    void injectIntoConnectedPage(tabId);
  }
});

// The grant is a trigger of its own, and usually the only one left. Chrome's
// permission dialog is a window that takes focus, and a popup that loses focus
// is closed — so on most desktops the popup that asked is already gone by the
// time the answer arrives, taking with it the code that would have acted on it.
chrome.permissions.onAdded.addListener((granted) => {
  void finishConnect(granted.origins ?? []);
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
    return message.type === PROBE ? answerProbe(message, sender) : acceptHandshake(message, sender);
  }
  if (!fromOurOwnSurfaces(sender)) {
    return { ignored: true };
  }
  switch (message?.type) {
    case "connection":
      return {
        connection: await connection(),
        version: VERSION,
        unanswered: await unanswered(),
        address: await typedAddress(),
      };
    case "about-to-connect":
      return announce(message);
    case "finish-connect":
      return finishConnect(null);
    case "declined":
      return forget();
    case "remember-address":
      return rememberAddress(message.address);
    case "disconnect":
      return disconnect();
    default:
      return { ignored: true };
  }
}

/** Announce only to the connected instance, even if an old injected bridge remains. */
async function answerProbe(message, sender) {
  const held = await connection();
  const origin = typeof message.instanceOrigin === "string" ? message.instanceOrigin : null;
  const connected =
    held !== null &&
    sender.id === chrome.runtime.id &&
    sender.frameId === 0 &&
    sender.origin === held.origin &&
    origin === held.origin;
  return connected ? { connected: true, version: VERSION } : { connected: false };
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

/**
 * What the popup is about to ask Chrome for, and what it means to do after.
 *
 * The popup says this before it asks, because after it asks it may not be
 * there to say anything: `chrome.permissions.request` opens a window of
 * Chrome's own, and the popup that opened it is closed when focus leaves. So
 * the intention is written down while there is still somewhere to write it
 * from, and finishing is left to whoever is still alive.
 */
async function announce(message) {
  await chrome.storage.session.set({
    [INTENT_KEY]: {
      origin: message.origin,
      how: message.how === "code" ? "code" : "page",
      code: typeof message.code === "string" ? message.code : "",
      announcedAt: Date.now(),
    },
  });
  return { announced: true };
}

/**
 * Do the announced connect, exactly once.
 *
 * Two arrivals follow one grant — the grant itself, and the popup that asked
 * for it, if the dialog left it standing. Whichever gets here first takes the
 * announcement and does the work; the other joins the same promise, and so
 * reads the same answer, rather than opening a second tab or spending a
 * one-time code twice.
 *
 * `origins` is what the grant carried, or `null` from the popup, which has no
 * need to match itself against what it just asked for.
 */
function finishConnect(origins) {
  finishing ??= take(origins).then(perform);
  const joined = finishing;
  void joined
    .catch(() => {})
    .finally(() => {
      if (finishing === joined) {
        finishing = null;
      }
    });
  return joined;
}

/** The connect in flight, so both arrivals share one of them. */
let finishing = null;

/** The announcement, if it is still good and this grant is the one it wanted. */
/**
 * Whether an announced connect is still sitting there unanswered.
 *
 * Chrome says nothing at all when a permission is declined — there is an event
 * for the grant and none for the refusal — and the popup that would have said
 * so is usually already closed by the dialog. What is left is the announcement
 * itself: only a connect that went through takes one, so one still here when a
 * popup opens is a connect that never got its grant.
 */
async function unanswered() {
  const stored = await chrome.storage.session.get(INTENT_KEY);
  const announced = stored[INTENT_KEY] ?? null;
  return announced !== null && Date.now() - announced.announcedAt <= INTENT_LIFETIME_MS;
}

/** Hold what is being typed, so the next popup opens where this one left off. */
async function rememberAddress(address) {
  await chrome.storage.session.set({
    [ADDRESS_KEY]: typeof address === "string" ? address : "",
  });
  return { remembered: true };
}

async function typedAddress() {
  const stored = await chrome.storage.session.get(ADDRESS_KEY);
  return stored[ADDRESS_KEY] ?? "";
}

/** Drop the announcement: a popup that outlived the dialog saw the refusal. */
async function forget() {
  await chrome.storage.session.remove(INTENT_KEY);
  return { forgotten: true };
}

async function take(origins) {
  const stored = await chrome.storage.session.get(INTENT_KEY);
  const announced = stored[INTENT_KEY] ?? null;
  if (announced === null) {
    return null;
  }
  if (Date.now() - announced.announcedAt > INTENT_LIFETIME_MS) {
    await chrome.storage.session.remove(INTENT_KEY);
    return null;
  }
  // A grant for some other origin is somebody else's business, and leaves the
  // announcement where it is.
  if (origins !== null && !origins.includes(originPattern(announced.origin))) {
    return null;
  }
  await chrome.storage.session.remove(INTENT_KEY);
  return announced;
}

/** Either way in, once the origin is granted. */
async function perform(announced) {
  if (announced === null) {
    // The other arrival got here first and is already done. Whatever it did is
    // in storage, which is where the popup reads its state from anyway.
    return { late: true };
  }
  return announced.how === "code"
    ? spendConnectCode(announced.origin, announced.code)
    : openTheConnectPage(announced.origin);
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
 * What is stored is dropped first and awaited; the access is handed back after,
 * and deliberately not awaited. Losing a host permission restarts this worker,
 * and a worker that goes down mid-message takes the answer with it — the popup
 * would be left showing a connection that no longer exists. So the answer goes
 * out first, and the disconnection stands on the storage either way: what the
 * extension will do is decided by what it has, not by what it may still reach.
 */
async function disconnect() {
  const held = await connection();
  await chrome.storage.local.remove(CONNECTION_KEY);
  await chrome.storage.session.remove(ATTEMPT_KEY);
  await chrome.storage.session.remove(INTENT_KEY);
  if (held !== null) {
    void giveTheAccessBack(held.origin);
  }
  return { connection: null, version: VERSION };
}

/**
 * Hand an origin back to Chrome, and say so when Chrome will not take it.
 *
 * A build installed by policy holds its origins as required permissions and
 * Chrome throws rather than drop one; a pattern it never granted is refused
 * more quietly, with a `false`. Neither undoes the disconnection, and both are
 * worth finding in the log rather than in a permission nobody meant to keep.
 */
async function giveTheAccessBack(origin) {
  const pattern = originPattern(origin);
  try {
    if (!(await chrome.permissions.remove({ origins: [pattern] }))) {
      console.warn(`step-by-step: Chrome kept the site access for ${pattern}`);
    }
  } catch (kept) {
    console.warn("step-by-step: the site access could not be given back", kept);
  }
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
  await injectIntoConnectedTabs(origin);
}

/** Put the version-announcing bridge into every already-open page of this instance. */
async function injectIntoConnectedTabs(origin) {
  const tabs = await chrome.tabs.query({ url: originPattern(origin) });
  await Promise.all(tabs.map((tab) => injectBridge(tab.id)));
}

/** Put the bridge into a newly loaded page only when it belongs to this instance. */
async function injectIntoConnectedPage(tabId) {
  const held = await connection();
  if (held === null) return;
  const tab = await chrome.tabs.get(tabId);
  if (typeof tab.url !== "string" || new URL(tab.url).origin !== held.origin) return;
  await injectBridge(tabId);
}

async function injectBridge(tabId) {
  if (typeof tabId !== "number") return;
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      func: pageBridge,
      args: [BRIDGE_PROTOCOL],
    });
  } catch (refused) {
    console.warn("step-by-step: a connected page could not be reached", refused);
  }
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
