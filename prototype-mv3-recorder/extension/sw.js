// PROTOTYPE — disposable. Recording coordinator: chrome.debugger attach, CDP
// role/name queries (timed), step assembly, navigation + download correlation.

let rec = null; // { tabId, startedAt, startUrl, steps, axCache, axTimings, notes }

const dbg = (method, params) =>
  new Promise((resolve, reject) =>
    chrome.debugger.sendCommand({ tabId: rec.tabId }, method, params || {}, (res) =>
      chrome.runtime.lastError ? reject(new Error(chrome.runtime.lastError.message)) : resolve(res)
    )
  );

function persist() {
  chrome.storage.local.set({ recording: rec });
}

async function start(tabId) {
  const tab = await chrome.tabs.get(tabId);
  rec = {
    tabId,
    startedAt: new Date().toISOString(),
    startUrl: tab.url,
    steps: [{ type: "navigate", url: tab.url, ts: Date.now(), origin: "recording-start" }],
    axCache: {},
    axTimings: [],
    notes: [],
  };
  await new Promise((resolve, reject) =>
    chrome.debugger.attach({ tabId }, "1.3", () =>
      chrome.runtime.lastError ? reject(new Error(chrome.runtime.lastError.message)) : resolve()
    )
  );
  await dbg("DOM.enable");
  await dbg("Accessibility.enable");
  persist();
}

async function stop() {
  if (!rec) return;
  try {
    await new Promise((r) => chrome.debugger.detach({ tabId: rec.tabId }, r));
  } catch {}
  rec.stoppedAt = new Date().toISOString();
  persist();
  rec = null;
}

// CDP role/name for the element flagged data-protorec=recId, timed. Runs at
// pointerdown/focusin so it usually beats a click-triggered navigation.
// Resolves the element via Runtime.evaluate -> objectId, avoiding DOM.getDocument
// nodeIds, which go stale across navigations and concurrent calls. axCache holds
// promises; step assembly awaits them (bounded) so a fast click cannot outrun
// its own prefetch.
function prefetchAx(recId) {
  rec.axCache[recId] = doPrefetchAx(recId);
}

async function doPrefetchAx(recId) {
  const entry = { ok: false };
  const t0 = performance.now();
  try {
    const { result: elObj } = await dbg("Runtime.evaluate", {
      expression: `document.querySelector('[data-protorec="${recId}"]')`,
    });
    if (!elObj.objectId) throw new Error("element not found via CDP");
    const { nodes } = await dbg("Accessibility.getPartialAXTree", {
      objectId: elObj.objectId,
      fetchRelatives: false,
    });
    const ax = nodes && nodes[0];
    entry.role = ax?.role?.value;
    entry.name = ax?.name?.value;
    entry.partialTreeMs = Math.round(performance.now() - t0);
    entry.ok = !!(entry.role !== undefined);
    if (entry.role && entry.name) {
      const t1 = performance.now();
      const { result: docObj } = await dbg("Runtime.evaluate", { expression: "document" });
      const { nodes: matches } = await dbg("Accessibility.queryAXTree", {
        objectId: docObj.objectId,
        role: entry.role,
        accessibleName: entry.name,
      });
      entry.uniqueInAxTree = (matches || []).filter((n) => !n.ignored).length === 1;
      entry.queryMs = Math.round(performance.now() - t1);
    }
  } catch (e) {
    entry.error = String(e.message || e);
  }
  entry.totalMs = Math.round(performance.now() - t0);
  const r = rec;
  if (r) {
    r.axTimings.push({ recId, ...entry });
    persist();
  }
  return entry;
}

const timeoutMs = (ms) => new Promise((r) => setTimeout(() => r(null), ms));

// Steps must land in interaction order even though ax lookups are async, so
// events flow through one serialized chain.
let evtChain = Promise.resolve();

function handleEvt(m) {
  evtChain = evtChain.then(() => assembleStep(m)).catch((e) => {
    rec?.notes.push(`assembleStep failed: ${String(e?.stack || e)}`);
    persist();
  });
}

async function assembleStep(m) {
  if (!rec) return;
  const cached = rec.axCache[m.recId];
  const ax = cached ? await Promise.race([cached, timeoutMs(750)]) : null;
  const selectors = [];
  if (ax?.ok && ax.role && ax.name && ax.name.trim())
    selectors.push({ kind: "role", role: ax.role, name: ax.name, verified: ax.uniqueInAxTree === true });
  // role+name ranks below testid, above everything else (Playwright score order)
  const cands = m.candidates || [];
  if (cands[0]?.kind === "testid") selectors.unshift(cands.shift());
  selectors.push(...cands);

  const step = { type: m.kind, selectors, url: m.url, ts: m.ts, meta: m.meta, ax };
  if (m.kind === "fill") {
    step.value = m.value;
    step.isPassword = !!m.isPassword;
  }
  if (m.kind === "select") {
    step.value = m.value;
    step.optionLabel = m.optionLabel;
  }
  if (m.kind === "extract") step.capturedText = m.capturedText;
  rec.steps.push(step);
  persist();
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.cmd === "start") {
    chrome.tabs.query({ active: true, currentWindow: true }).then(([tab]) =>
      start(tab.id).then(
        () => sendResponse({ ok: true }),
        (e) => sendResponse({ ok: false, error: String(e.message || e) })
      )
    );
    return true;
  }
  if (msg.cmd === "stop") {
    stop().then(() => sendResponse({ ok: true }));
    return true;
  }
  if (msg.cmd === "status") {
    sendResponse({ active: !!rec, steps: rec?.steps.length || 0 });
    return;
  }

  if (!rec || sender.tab?.id !== rec.tabId) return;
  if (msg.type === "ax-prefetch") prefetchAx(msg.recId);
  else if (msg.type === "evt") handleEvt(msg);
  else if (msg.type === "cs-error") {
    rec.notes.push(`content-script error (${msg.where}): ${msg.error}`);
    persist();
  } else if (msg.type === "cs-hello") {
    rec.notes.push(`content script alive on ${msg.url}`);
    persist();
  }
});

chrome.webNavigation.onCommitted.addListener((e) => {
  if (!rec || e.tabId !== rec.tabId || e.frameId !== 0) return;
  // through the same chain as interaction events, so order is interaction order
  evtChain = evtChain.then(() => commitNavigation(e));
});

function commitNavigation(e) {
  if (!rec) return;
  const last = rec.steps[rec.steps.length - 1];
  // A navigation right after a click with a link/form transition belongs to the
  // click as its asserted outcome, not as a standalone step.
  if (
    last &&
    last.type === "click" &&
    Date.now() - last.ts < 3000 &&
    ["link", "form_submit"].includes(e.transitionType)
  ) {
    last.assertedNavigation = e.url;
  } else if (e.url !== rec.steps.find((s) => s.type === "navigate")?.url || rec.steps.length > 1) {
    rec.steps.push({ type: "navigate", url: e.url, transition: e.transitionType, ts: Date.now() });
  }
  persist();
}

chrome.webNavigation.onHistoryStateUpdated.addListener((e) => {
  if (!rec || e.tabId !== rec.tabId || e.frameId !== 0) return;
  rec.steps.push({ type: "navigate", url: e.url, transition: "history-state", ts: Date.now() });
  persist();
});

chrome.downloads.onCreated.addListener((item) => {
  if (!rec) return;
  evtChain = evtChain.then(() => {
    if (!rec) return;
    const last = rec.steps[rec.steps.length - 1];
    const dl = { url: item.url, filename: item.filename || null, ts: Date.now() };
    if (last && last.type === "click" && Date.now() - last.ts < 5000) last.download = dl;
    else rec.steps.push({ type: "download", ...dl });
    persist();
  });
});

chrome.downloads.onChanged.addListener((delta) => {
  if (!delta.filename) return;
  chrome.storage.local.get("recording").then(({ recording }) => {
    if (!recording) return;
    for (const s of recording.steps) {
      if (s.download && !s.download.filename) s.download.filename = delta.filename.current;
      if (s.type === "download" && !s.filename) s.filename = delta.filename.current;
    }
    chrome.storage.local.set({ recording });
    if (rec) rec.steps = recording.steps;
  });
});

chrome.debugger.onDetach.addListener((source, reason) => {
  if (rec && source.tabId === rec.tabId) {
    rec.notes.push(`debugger detached mid-recording: ${reason}`);
    rec.stoppedAt = new Date().toISOString();
    persist();
    rec = null;
  }
});
