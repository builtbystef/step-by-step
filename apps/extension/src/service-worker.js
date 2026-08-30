import {
  ACCEPTED,
  CHANNEL,
  HANDSHAKE,
  PROBE,
  READY,
  RECORDING_FINISHED,
  RECORDING_PENDING,
  RECORDING_PENDING_ACCEPTED,
  RECORDING_STATUS,
  RECORDING_TOKEN,
  RECORDING_TOKEN_EXPIRED,
  REPICK_CANDIDATES,
  isProtocolMessage,
  judgeHandshake,
  mintNonce,
} from "./lib/handshake.js";
import { originPattern, readInstanceUrl } from "./lib/instance.js";
import { pageBridge } from "./lib/page-bridge.js";
import { bindSecretSteps, captureChoices, readPendingRecording } from "./lib/recording.js";

const CONNECTION_KEY = "connection";

const ATTEMPT_KEY = "connect-attempt";

const INTENT_KEY = "connect-intent";

const ADDRESS_KEY = "typed-address";

const CONNECT_PATH = "/connect";

const CONNECT_ENDPOINT = "/api/extension/connect";

const ATTEMPT_LIFETIME_MS = 5 * 60 * 1000;

const INTENT_LIFETIME_MS = 2 * 60 * 1000;

const CODE_LENGTH_LIMIT = 64;

const VERSION = chrome.runtime.getManifest().version;

const BRIDGE_PROTOCOL = {
  channel: CHANNEL,
  handshake: HANDSHAKE,
  probe: PROBE,
  ready: READY,
  accepted: ACCEPTED,
  recordingPending: RECORDING_PENDING,
  recordingPendingAccepted: RECORDING_PENDING_ACCEPTED,
  recordingStatus: RECORDING_STATUS,
  recordingTokenExpired: RECORDING_TOKEN_EXPIRED,
  recordingToken: RECORDING_TOKEN,
  recordingFinished: RECORDING_FINISHED,
  repickCandidates: REPICK_CANDIDATES,
  version: VERSION,
};

chrome.runtime.onMessage.addListener((message, sender, respond) => {
  answer(message, sender).then(respond, (failure) => {
    console.warn("step-by-step: a message could not be answered", failure);
    respond({ error: "failed" });
  });
  return true;
});

chrome.tabs.onUpdated.addListener((tabId, change) => {
  if (change.status === "complete") {
    void injectIntoTheConnectPage(tabId);
    void injectIntoConnectedPage(tabId);
  }
});

chrome.permissions.onAdded.addListener((granted) => {
  void finishConnect(granted.origins ?? []);
  void finishRecordingStart(granted.origins ?? []);
});

chrome.webNavigation.onBeforeNavigate.addListener((details) => {
  if (details.frameId === 0) void enqueueRecording(captureOpenFrameStorage);
});

chrome.webNavigation.onCommitted.addListener((details) => {
  void enqueueRecording(() => rememberVisitedHost(details));
  if (details.frameId === 0) void enqueueRecording(() => recordNavigation(details));
});

chrome.debugger.onDetach.addListener((source) => {
  void endRecordingAfterDetach(source.tabId);
});

chrome.downloads.onCreated.addListener(() => {
  void enqueueRecording(recordRecentClickAsDownload);
});

async function answer(message, sender) {
  if (isProtocolMessage(message)) {
    if (message.type === PROBE) return answerProbe(message, sender);
    if (message.type === HANDSHAKE) return acceptHandshake(message, sender);
    return acceptRecordingPageMessage(message, sender);
  }
  if (message?.type === "recorder-ax" || message?.type === "recorder-event") {
    return acceptRecorderMessage(message, sender);
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
        recording: await activeRecording(),
      };
    case "about-to-connect":
      return announce(message);
    case "finish-connect":
      return finishConnect(null);
    case "declined":
      return forget();
    case "remember-address":
      return rememberAddress(message.address);
    case "about-to-start-recording":
      return announceRecordingStart(message);
    case "finish-recording-start":
      return finishRecordingStart(null);
    case "recording-state":
      return { recording: await activeRecording() };
    case "stop-recording":
      return stopRecording();
    case "discard-recording":
      return discardRecording();
    case "finalize-recording":
      return finalizeRecording(message.bindings, message.authSelections);
    case "arm-extract":
      return armExtract(message);
    case "disconnect":
      return disconnect();
    default:
      return { ignored: true };
  }
}

async function acceptRecordingPageMessage(message, sender) {
  const held = await connection();
  if (
    held === null ||
    sender.id !== chrome.runtime.id ||
    sender.frameId !== 0 ||
    sender.origin !== held.origin
  ) {
    return { ignored: true };
  }
  if (message.type === RECORDING_STATUS) {
    const active = await activeRecording();
    return active?.tokenExpired === true
      ? { type: RECORDING_TOKEN_EXPIRED, sessionId: active.sessionId }
      : { type: null };
  }
  if (message.type === RECORDING_PENDING) {
    const current = await activeRecording();
    if (current !== null && current.state !== "pending") {
      return { accepted: false, reason: "recording-in-progress" };
    }
    const pending = readPendingRecording(message);
    if (pending === null || pending.backendOrigin !== held.origin) {
      return { accepted: false };
    }
    await chrome.storage.local.set({
      [RECORDING_KEY]:
        pending.mode === "repick"
          ? {
              state: "pending",
              mode: "repick",
              sessionId: pending.sessionId,
              token: pending.token,
              backendOrigin: pending.backendOrigin,
              workflowId: pending.workflowId,
              workflowName: pending.workflowName,
              stepId: pending.stepId,
              steps: [],
              checkpointSeq: 0,
            }
          : {
              state: "pending",
              mode: "record",
              sessionId: pending.sessionId,
              token: pending.token,
              backendOrigin: pending.backendOrigin,
              workflowId: pending.workflowId,
              workflowName: pending.workflowName,
              variables: pending.variables,
              secrets: pending.secrets,
              steps: [],
              visitedHosts: [],
              storageByOrigin: {},
              authChoices: [],
              checkpointSeq: 0,
            },
    });
    return { accepted: true, type: RECORDING_PENDING_ACCEPTED, sessionId: pending.sessionId };
  }
  if (message.type === RECORDING_TOKEN) {
    const active = await activeRecording();
    if (
      active === null ||
      active.sessionId !== message.sessionId ||
      typeof message.token !== "string"
    ) {
      return { accepted: false };
    }
    active.token = message.token;
    delete active.tokenExpired;
    await chrome.storage.local.set({ [RECORDING_KEY]: active });
    if (active.checkpointSeq > 0) await sendCheckpoint(active);
    return { accepted: true };
  }
  return { ignored: true };
}

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

function finishConnect(origins) {
  // The permission event and popup share one connection attempt.
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

let finishing = null;

async function unanswered() {
  const stored = await chrome.storage.session.get(INTENT_KEY);
  const announced = stored[INTENT_KEY] ?? null;
  return announced !== null && Date.now() - announced.announcedAt <= INTENT_LIFETIME_MS;
}

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
  if (origins !== null && !origins.includes(originPattern(announced.origin))) {
    return null;
  }
  await chrome.storage.session.remove(INTENT_KEY);
  return announced;
}

async function perform(announced) {
  if (announced === null) {
    return { late: true };
  }
  return announced.how === "code"
    ? spendConnectCode(announced.origin, announced.code)
    : openTheConnectPage(announced.origin);
}

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

  // The tab may finish loading before the attempt is stored.
  await injectIfLoaded(tab.id);
  return { opened: true };
}

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

async function disconnect() {
  const held = await connection();
  await chrome.storage.local.remove(CONNECTION_KEY);
  await chrome.storage.session.remove(ATTEMPT_KEY);
  await chrome.storage.session.remove(INTENT_KEY);
  if (held !== null) {
    // Removing permission can restart the worker, so answer first.
    void giveTheAccessBack(held.origin);
  }
  return { connection: null, version: VERSION };
}

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

async function injectIfLoaded(tabId) {
  const tab = await chrome.tabs.get(tabId);
  if (tab.status === "complete") {
    await injectIntoTheConnectPage(tabId);
  }
}

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

async function injectIntoConnectedTabs(origin) {
  const tabs = await chrome.tabs.query({ url: originPattern(origin) });
  await Promise.all(tabs.map((tab) => injectBridge(tab.id)));
}

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

function fromOurOwnSurfaces(sender) {
  return (
    sender.id === chrome.runtime.id && (sender.url ?? "").startsWith(chrome.runtime.getURL(""))
  );
}

function canonical(origin) {
  if (typeof origin !== "string") {
    return null;
  }
  const read = readInstanceUrl(origin);
  return read.origin === origin ? origin : null;
}

function permitted(origin) {
  return chrome.permissions.contains({ origins: [originPattern(origin)] });
}

const RECORDING_KEY = "active-recording";
const RECORDING_INTENT_KEY = "recording-start-intent";
const AX_WAIT_MS = 750;
const DOWNLOAD_WINDOW_MS = 5000;
const CLOSED_SHADOW_WARNING =
  "This part of the page is sealed off, so the workflow may not be able to use it later. The step was recorded anyway.";
let recordingQueue = Promise.resolve();
const accessibilityQueries = new Map();

function enqueueRecording(work) {
  recordingQueue = recordingQueue.then(work).catch((failure) => {
    console.warn("step-by-step: recorder event failed", failure);
  });
  return recordingQueue;
}

async function announceRecordingStart(message) {
  if (typeof message.targetTabId !== "number" || typeof message.targetUrl !== "string") {
    return { announced: false };
  }
  await chrome.storage.session.set({
    [RECORDING_INTENT_KEY]: {
      targetTabId: message.targetTabId,
      targetUrl: message.targetUrl,
      announcedAt: Date.now(),
    },
  });
  return { announced: true };
}

let startingRecording = null;

function finishRecordingStart(origins) {
  startingRecording ??= takeRecordingIntent(origins).then((intent) =>
    intent === null ? { late: true } : startRecording(intent),
  );
  const joined = startingRecording;
  void joined.finally(() => {
    if (startingRecording === joined) startingRecording = null;
  });
  return joined;
}

async function takeRecordingIntent(origins) {
  const stored = await chrome.storage.session.get(RECORDING_INTENT_KEY);
  const intent = stored[RECORDING_INTENT_KEY] ?? null;
  if (intent === null || Date.now() - intent.announcedAt > INTENT_LIFETIME_MS) {
    await chrome.storage.session.remove(RECORDING_INTENT_KEY);
    return null;
  }
  const targetOrigin = new URL(intent.targetUrl).origin;
  if (origins !== null && !origins.includes(originPattern(targetOrigin))) return null;
  await chrome.storage.session.remove(RECORDING_INTENT_KEY);
  return intent;
}

async function startRecording(message) {
  const active = await activeRecording();
  if (
    active?.state !== "pending" ||
    typeof message.targetUrl !== "string" ||
    typeof active.token !== "string" ||
    typeof active.backendOrigin !== "string"
  ) {
    return { started: false, reason: "no-pending-recording" };
  }
  const held = await connection();
  if (held?.origin !== active.backendOrigin) return { started: false, reason: "wrong-instance" };
  const tab =
    typeof message.targetTabId === "number"
      ? await chrome.tabs.get(message.targetTabId)
      : (await chrome.tabs.query({ url: message.targetUrl })).find(
          (candidate) => candidate.url === message.targetUrl,
        );
  if (typeof tab?.id !== "number" || tab.url !== message.targetUrl) {
    return { started: false, reason: "target-gone" };
  }
  if (!(await permitted(new URL(message.targetUrl).origin))) {
    return { started: false, reason: "not-permitted" };
  }

  await debuggerAttach(tab.id);
  await debuggerCommand(tab.id, "Accessibility.enable");
  active.tabId = tab.id;
  active.state = "recording";
  active.visitedHosts = [new URL(message.targetUrl).hostname];
  await chrome.storage.local.set({ [RECORDING_KEY]: active });
  await injectRecorder(tab.id);
  await captureOpenFrameStorage();
  return { started: true };
}

async function armExtract(message) {
  const active = await activeRecording();
  if (active === null || !["scalar", "list"].includes(message.mode)) return { armed: false };
  if (typeof message.outputName !== "string" || message.outputName.trim() === "") {
    return { armed: false };
  }
  const extract = {
    outputName: message.outputName,
    mode: message.mode,
    ...(typeof message.attribute === "string" ? { attribute: message.attribute } : {}),
    ...(message.mode === "list" && Array.isArray(message.fields) ? { fields: message.fields } : {}),
  };
  try {
    await chrome.tabs.sendMessage(active.tabId, { type: "recorder-arm-extract", extract });
  } catch {
    return { armed: false };
  }
  return { armed: true };
}

async function stopRecording() {
  const active = await activeRecording();
  if (active?.mode === "repick") {
    if (active.state === "recording") {
      try {
        await debuggerDetach(active.tabId);
      } catch {}
    }
    accessibilityQueries.clear();
    await chrome.storage.local.remove(RECORDING_KEY);
    return { stopped: true };
  }
  if (active?.state === "recording") {
    await captureOpenFrameStorage();
    const fresh = await activeRecording();
    if (fresh !== null) Object.assign(active, fresh);
    active.authChoices = await loadAuthChoices(active);
    active.state = "ended";
    active.endedReason = "stopped";
    active.endedAt = new Date().toISOString();
    await chrome.storage.local.set({ [RECORDING_KEY]: active });
    try {
      await debuggerDetach(active.tabId);
    } catch {}
  }
  accessibilityQueries.clear();
  return { stopped: true };
}

async function discardRecording() {
  const active = await activeRecording();
  await chrome.storage.local.remove(RECORDING_KEY);
  if (active?.state === "recording") void debuggerDetach(active.tabId);
  accessibilityQueries.clear();
  return { discarded: true };
}

async function finalizeRecording(bindings, authSelections = []) {
  const active = await activeRecording();
  if (active === null || active.state !== "ended" || !Array.isArray(bindings)) {
    return { saved: false, reason: "not-ended" };
  }
  const resolved = await resolveRecordingSecrets(active, bindings);
  if (!resolved.ok) return resolved.answer;
  let document;
  try {
    document = bindSecretSteps(active.steps, resolved.bindings, active.variables ?? []);
  } catch (failure) {
    return { saved: false, reason: "needs-secret", message: failure.message };
  }
  const selected = Array.isArray(authSelections)
    ? authSelections.filter((choice) => choice.checked === true)
    : [];
  if (selected.length > 0) {
    const uploaded = await uploadAuthStates(active, selected);
    if (!uploaded.ok) return uploaded.answer;
  }
  let response;
  try {
    response = await fetch(
      `${active.backendOrigin}/api/recording-sessions/${encodeURIComponent(active.sessionId)}/finalize`,
      {
        method: "POST",
        headers: { Authorization: active.token, "Content-Type": "application/json" },
        body: JSON.stringify(document),
      },
    );
  } catch {
    return { saved: false, reason: "unreachable" };
  }
  if (response.status === 401) {
    await markTokenExpired(active);
    return { saved: false, reason: "token-expired" };
  }
  if (!response.ok) return { saved: false, reason: "refused" };
  await chrome.storage.local.remove(RECORDING_KEY);
  await broadcastRecording(RECORDING_FINISHED, active.sessionId);
  return { saved: true };
}

async function resolveRecordingSecrets(active, bindings) {
  const resolved = [];
  for (const binding of bindings) {
    if (binding?.secret && typeof binding.secret.id === "string") {
      resolved.push(binding);
      continue;
    }
    if (typeof binding?.create?.name !== "string" || typeof binding.create.value !== "string") {
      resolved.push(binding);
      continue;
    }
    let response;
    try {
      response = await fetch(
        `${active.backendOrigin}/api/recording-sessions/${encodeURIComponent(active.sessionId)}/secrets`,
        {
          method: "POST",
          headers: { Authorization: active.token, "Content-Type": "application/json" },
          body: JSON.stringify({ name: binding.create.name, value: binding.create.value }),
        },
      );
    } catch {
      return { ok: false, answer: { saved: false, reason: "unreachable" } };
    }
    if (response.status === 401) {
      await markTokenExpired(active);
      return { ok: false, answer: { saved: false, reason: "token-expired" } };
    }
    if (!response.ok) {
      let refusal = null;
      try {
        refusal = await response.json();
      } catch {}
      if (response.status === 409 && refusal?.code === "name_taken") {
        return {
          ok: false,
          answer: {
            saved: false,
            reason: "name-taken",
            message: "That Secret name is already used. Rename it or pick the existing Secret.",
          },
        };
      }
      return { ok: false, answer: { saved: false, reason: "refused" } };
    }
    const secret = await response.json();
    resolved.push({ ...binding, secret });
  }
  return { ok: true, bindings: resolved };
}

async function endRecordingAfterDetach(tabId) {
  const active = await activeRecording();
  if (active?.tabId !== tabId || active.state !== "recording") return;
  if (active.mode === "repick") {
    accessibilityQueries.clear();
    await chrome.storage.local.remove(RECORDING_KEY);
    return;
  }
  active.authChoices = await loadAuthChoices(active);
  active.state = "ended";
  active.endedReason = "debugger-detached";
  active.endedAt = new Date().toISOString();
  await chrome.storage.local.set({ [RECORDING_KEY]: active });
  accessibilityQueries.clear();
}

async function activeRecording() {
  const stored = await chrome.storage.local.get(RECORDING_KEY);
  return stored[RECORDING_KEY] ?? null;
}

async function injectRecorder(tabId) {
  try {
    await chrome.scripting.executeScript({
      target: { tabId, allFrames: true },
      files: ["recorder-content.js"],
    });
  } catch (refused) {
    console.warn("step-by-step: recorder could not enter every permitted frame", refused);
  }
}

async function acceptRecorderMessage(message, sender) {
  const active = await activeRecording();
  if (
    active === null ||
    active.state !== "recording" ||
    sender.id !== chrome.runtime.id ||
    sender.tab?.id !== active.tabId ||
    typeof sender.frameId !== "number" ||
    typeof message.correlation !== "string" ||
    typeof message.pageLoad !== "string" ||
    !message.correlation.startsWith(`${message.pageLoad}:`)
  ) {
    return { ignored: true };
  }
  const key = `${sender.frameId}:${message.correlation}`;
  if (message.type === "recorder-ax") {
    accessibilityQueries.set(
      key,
      queryAccessibility(active.tabId, sender.frameId, message.correlation),
    );
  } else {
    void enqueueRecording(() => assembleInteraction(active.tabId, key, message));
  }
  return { accepted: true };
}

async function queryAccessibility(tabId, frameId, correlation) {
  const selector = `[data-step-by-step-correlation=${JSON.stringify(correlation)}]`;
  try {
    const evaluated = await debuggerCommand(tabId, "Runtime.evaluate", {
      expression: `document.querySelector(${JSON.stringify(selector)})`,
    });
    const objectId = evaluated.result?.objectId;
    if (!objectId) return null;
    const described = await debuggerCommand(tabId, "DOM.describeNode", {
      objectId,
      depth: 0,
      pierce: true,
    });
    const unsupported = described.node?.shadowRoots?.some(
      (root) => root.shadowRootType === "closed",
    )
      ? { reason: "closed-shadow-root", warning: CLOSED_SHADOW_WARNING }
      : null;
    if (unsupported !== null) {
      void chrome.tabs
        .sendMessage(tabId, { type: "recorder-warning", unsupported }, { frameId })
        .catch(() => {});
    }
    const partial = await debuggerCommand(tabId, "Accessibility.getPartialAXTree", {
      objectId,
      fetchRelatives: false,
    });
    const node = partial.nodes?.find((candidate) => !candidate.ignored);
    const role = node?.role?.value;
    const name = node?.name?.value;
    if (typeof role !== "string" || typeof name !== "string" || name.trim() === "") {
      return { role: null, unsupported };
    }
    const documentObject = await debuggerCommand(tabId, "Runtime.evaluate", {
      expression: "document",
    });
    const matches = await debuggerCommand(tabId, "Accessibility.queryAXTree", {
      objectId: documentObject.result?.objectId,
      role,
      accessibleName: name,
    });
    if ((matches.nodes ?? []).filter((candidate) => !candidate.ignored).length !== 1) {
      return { role: null, unsupported };
    }
    return {
      role: { kind: "role", value: `${role}[name=${JSON.stringify(name)}]` },
      unsupported,
    };
  } catch {
    return null;
  }
}

async function assembleInteraction(tabId, key, message) {
  const active = await activeRecording();
  if (active?.tabId !== tabId) return;
  const pending = accessibilityQueries.get(key);
  const prefetched = pending
    ? await Promise.race([
        pending,
        new Promise((resolve) => setTimeout(() => resolve(null), AX_WAIT_MS)),
      ])
    : null;
  accessibilityQueries.delete(key);
  const candidates = Array.isArray(message.candidates) ? [...message.candidates] : [];
  if (prefetched?.role) {
    candidates.splice(candidates[0]?.kind === "testid" ? 1 : 0, 0, prefetched.role);
  }
  if (active.mode === "repick") {
    await completeRepick(active, candidates);
    return;
  }

  const description =
    typeof message.description === "string" && message.description
      ? message.description
      : "element";
  const step = {
    id: crypto.randomUUID(),
    type: message.event,
    label:
      message.event === "type"
        ? `Type into ${description}`
        : message.event === "select"
          ? `Select ${description}`
          : message.event === "extract"
            ? `Extract ${description}`
            : `Click ${description}`,
    optional: false,
    disabled: false,
    screenshot: false,
    payload: {
      target: {
        candidates,
        ...(message.unsupported || prefetched?.unsupported
          ? { unsupported: message.unsupported ?? prefetched.unsupported }
          : {}),
      },
      ...(["type", "select"].includes(message.event) ? { value: message.value ?? "" } : {}),
      ...(message.event === "extract" && message.extract ? message.extract : {}),
    },
  };
  if (message.needsSecret === true) step.needsSecret = true;
  active.steps.push(step);
  if (message.event === "click") {
    active.recentClick = { stepId: step.id, at: Date.now() };
  }
  await checkpoint(active);
}

async function completeRepick(active, candidates) {
  await broadcastRecording(REPICK_CANDIDATES, active.sessionId, {
    stepId: active.stepId,
    candidates,
  });
  try {
    await debuggerDetach(active.tabId);
  } catch {}
  accessibilityQueries.clear();
  await chrome.storage.local.remove(RECORDING_KEY);
}

async function recordRecentClickAsDownload() {
  const active = await activeRecording();
  const recent = active?.recentClick;
  if (
    active?.state !== "recording" ||
    recent === undefined ||
    Date.now() - recent.at > DOWNLOAD_WINDOW_MS
  )
    return;
  const step = active.steps.find((candidate) => candidate.id === recent.stepId);
  if (step?.type !== "click") return;
  step.type = "download";
  step.label = step.label.replace(/^Click /, "Download ");
  step.payload = { target: step.payload.target };
  delete active.recentClick;
  await checkpoint(active);
}

async function rememberVisitedHost(details) {
  const active = await activeRecording();
  if (active === null || active.tabId !== details.tabId || !details.url.startsWith("http")) return;
  const host = new URL(details.url).hostname;
  active.visitedHosts ??= [];
  if (!active.visitedHosts.includes(host)) active.visitedHosts.push(host);
  await chrome.storage.local.set({ [RECORDING_KEY]: active });
}

async function captureOpenFrameStorage() {
  const active = await activeRecording();
  if (active?.state !== "recording" || typeof active.tabId !== "number") return;
  let frames;
  try {
    frames = await chrome.webNavigation.getAllFrames({ tabId: active.tabId });
  } catch {
    return;
  }
  for (const frame of frames ?? []) {
    try {
      const snapshot = await chrome.tabs.sendMessage(
        active.tabId,
        { type: "recorder-read-storage" },
        { frameId: frame.frameId },
      );
      if (typeof snapshot?.origin !== "string" || !snapshot.origin.startsWith("http")) continue;
      active.storageByOrigin ??= {};
      active.storageByOrigin[snapshot.origin] = {
        localStorage: snapshot.localStorage ?? [],
        sessionStorage: snapshot.sessionStorage ?? [],
      };
      const host = new URL(snapshot.origin).hostname;
      active.visitedHosts ??= [];
      if (!active.visitedHosts.includes(host)) active.visitedHosts.push(host);
    } catch {}
  }
  await chrome.storage.local.set({ [RECORDING_KEY]: active });
}

async function loadAuthChoices(active) {
  if ((active.visitedHosts ?? []).length === 0) return [];
  try {
    const response = await fetch(
      `${active.backendOrigin}/api/recording-sessions/${encodeURIComponent(active.sessionId)}/auth-state-options`,
      {
        method: "POST",
        headers: { Authorization: active.token, "Content-Type": "application/json" },
        body: JSON.stringify({ hosts: active.visitedHosts }),
      },
    );
    if (response.status === 401) await markTokenExpired(active);
    if (!response.ok) return [];
    return captureChoices(await response.json());
  } catch {
    return [];
  }
}

function belongsToDomain(origin, domain) {
  const host = new URL(origin).hostname;
  return host === domain || host.endsWith(`.${domain}`);
}

function chromeCookie(cookie) {
  const sameSites = { lax: "Lax", strict: "Strict", no_restriction: "None" };
  const { expirationDate, sameSite, ...rest } = cookie;
  return {
    ...rest,
    ...(typeof expirationDate === "number" ? { expires: expirationDate } : {}),
    ...(sameSites[sameSite] ? { sameSite: sameSites[sameSite] } : {}),
  };
}

async function uploadAuthStates(active, selected) {
  const captures = [];
  for (const choice of selected) {
    const origins = Object.entries(active.storageByOrigin ?? {}).filter(([origin]) =>
      belongsToDomain(origin, choice.domain),
    );
    const cookieGroups = await Promise.all([
      chrome.cookies.getAll({ domain: choice.domain }),
      ...origins.map(([origin]) => chrome.cookies.getAll({ url: `${origin}/` })),
    ]);
    const cookies = [
      ...new Map(
        cookieGroups
          .flat()
          .map((cookie) => [
            `${cookie.storeId}:${cookie.partitionKey?.topLevelSite ?? ""}:${cookie.domain}:${cookie.path}:${cookie.name}`,
            cookie,
          ]),
      ).values(),
    ];
    captures.push({
      domain: choice.domain,
      scope: choice.scope === "personal" ? "personal" : "organization",
      cookies: cookies.map(chromeCookie),
      origins: origins.map(([origin, values]) => ({
        origin,
        local_storage: values.localStorage ?? [],
      })),
      session_storage: origins.map(([origin, values]) => ({
        origin,
        items: values.sessionStorage ?? [],
      })),
    });
  }
  try {
    const response = await fetch(
      `${active.backendOrigin}/api/recording-sessions/${encodeURIComponent(active.sessionId)}/auth-states`,
      {
        method: "POST",
        headers: { Authorization: active.token, "Content-Type": "application/json" },
        body: JSON.stringify({ captures }),
      },
    );
    if (response.status === 401) {
      await markTokenExpired(active);
      return { ok: false, answer: { saved: false, reason: "token-expired" } };
    }
    if (!response.ok) return { ok: false, answer: { saved: false, reason: "refused" } };
    return { ok: true };
  } catch {
    return { ok: false, answer: { saved: false, reason: "unreachable" } };
  }
}

async function recordNavigation(details) {
  const active = await activeRecording();
  if (active === null || active.tabId !== details.tabId) return;
  if (active.mode === "repick") {
    await injectRecorder(active.tabId);
    return;
  }
  const previous = active.steps.at(-1);
  if (previous?.type === "click" && ["link", "form_submit"].includes(details.transitionType)) {
    previous.payload.assertedNavigation = true;
  } else {
    active.steps.push({
      id: crypto.randomUUID(),
      type: "navigate",
      label: `Navigate to ${new URL(details.url).hostname}`,
      optional: false,
      disabled: false,
      screenshot: false,
      payload: { url: details.url },
    });
  }
  await checkpoint(active);
  await injectRecorder(active.tabId);
}

async function checkpoint(active) {
  active.checkpointSeq += 1;
  await chrome.storage.local.set({ [RECORDING_KEY]: active });
  await sendCheckpoint(active);
}

async function sendCheckpoint(active) {
  const response = await fetch(
    `${active.backendOrigin}/api/recording-sessions/${encodeURIComponent(active.sessionId)}/checkpoint`,
    {
      method: "POST",
      headers: {
        Authorization: active.token,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ seq: active.checkpointSeq, steps: active.steps }),
    },
  );
  if (response.status === 401) {
    await markTokenExpired(active);
    return;
  }
  if (!response.ok) throw new Error(`checkpoint refused (${response.status})`);
}

async function markTokenExpired(active) {
  active.tokenExpired = true;
  await chrome.storage.local.set({ [RECORDING_KEY]: active });
  await broadcastRecording(RECORDING_TOKEN_EXPIRED, active.sessionId);
}

async function broadcastRecording(type, sessionId, extra = {}) {
  const held = await connection();
  if (held === null) return;
  const tabs = await chrome.tabs.query({ url: originPattern(held.origin) });
  await Promise.all(
    tabs.map((tab) =>
      typeof tab.id === "number"
        ? chrome.tabs.sendMessage(tab.id, { type, sessionId, ...extra }).catch(() => {})
        : Promise.resolve(),
    ),
  );
}

function debuggerAttach(tabId) {
  return new Promise((resolve, reject) => {
    chrome.debugger.attach({ tabId }, "1.3", () => {
      const failure = chrome.runtime.lastError;
      if (failure) reject(new Error(failure.message));
      else resolve();
    });
  });
}

function debuggerDetach(tabId) {
  return new Promise((resolve) => chrome.debugger.detach({ tabId }, resolve));
}

function debuggerCommand(tabId, method, params = {}) {
  return new Promise((resolve, reject) => {
    chrome.debugger.sendCommand({ tabId }, method, params, (result) => {
      const failure = chrome.runtime.lastError;
      if (failure) reject(new Error(failure.message));
      else resolve(result ?? {});
    });
  });
}
