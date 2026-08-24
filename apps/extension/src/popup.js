/**
 * The popup: the one surface where a person connects this extension to their
 * instance, and the only place a permission can be asked for.
 *
 * Chrome grants an optional host permission only from a user gesture, so
 * `chrome.permissions.request` is called from the click itself, before
 * anything is awaited — an `await` first would spend the gesture and the
 * request would be refused without ever being shown.
 *
 * And asking can cost this popup its life: the dialog is a window of Chrome's
 * own, and a popup that loses focus is closed. So the click tells the worker
 * what it is about to do before it asks, and the worker finishes it on the
 * grant. Nothing here is the only way the connect can complete.
 *
 * The connect code is the second way in rather than a way around the grant:
 * the extension has to be allowed to reach the instance either way, so that
 * button asks for the same origin from its own click.
 */

import { originPattern, readInstanceUrl } from "./lib/instance.js";

const ADDRESS_PROBLEMS = {
  empty: "Enter the address of your Step by Step instance.",
  malformed: "That does not look like a web address.",
  "unsupported-scheme": "An instance is reached over http or https.",
};

/**
 * What a declined grant leaves behind, said whenever it is found unanswered.
 *
 * Chrome raises no event for a refusal and the dialog usually closes the popup
 * that asked, so this is as often said by the next popup to open as by the one
 * that was there.
 */
const DECLINED =
  "Step by Step needs Chrome's permission for that address before it can connect. " +
  "Try again, and choose Allow.";

const REFUSALS = {
  "not-permitted": "Chrome did not allow this extension to work on that address.",
  "not-an-instance": "That does not look like a web address.",
  "bad-code": "That code is not valid any more. Show a new one in the app.",
  unreachable: "That address did not answer. Check it, and that the instance is running.",
  failed: "Something went wrong. Try again.",
};

const view = {
  connected: document.querySelector("#connected"),
  connect: document.querySelector("#connect"),
  instance: document.querySelector("#instance"),
  address: document.querySelector("#address"),
  code: document.querySelector("#code"),
  fallback: document.querySelector("#code-fallback"),
  note: document.querySelector("#note"),
  version: document.querySelector("#version"),
  pending: document.querySelector("#recording-pending"),
  pendingWorkflow: document.querySelector("#pending-workflow"),
  active: document.querySelector("#recording-active"),
  activeWorkflow: document.querySelector("#active-workflow"),
  save: document.querySelector("#recording-save"),
  saveWorkflow: document.querySelector("#save-workflow"),
  saveSummary: document.querySelector("#save-summary"),
  bindings: document.querySelector("#secret-bindings"),
  secretVariables: document.querySelector("#secret-variables"),
};

// Read the tab while the popup is opening. The later click must call
// permissions.request directly from its user gesture, before awaiting anything.
let targetTab = null;
void chrome.tabs.query({ active: true, lastFocusedWindow: true }).then(([tab]) => {
  targetTab = tab ?? null;
});

document.querySelector("#connect-button").addEventListener("click", () => {
  connect("page");
});

document.querySelector("#code-button").addEventListener("click", () => {
  connect("code");
});

document.querySelector("#record-button").addEventListener("click", () => {
  startPendingRecording();
});

document.querySelector("#stop-button").addEventListener("click", () => {
  void ask("stop-recording")
    .then(() => ask("connection"))
    .then(show);
});

document.querySelector("#discard-button").addEventListener("click", () => {
  if (!confirm("Discard this recording? Its captured Steps will be lost.")) return;
  void ask("discard-recording")
    .then(() => ask("connection"))
    .then(show);
});

document.querySelector("#save-button").addEventListener("click", () => {
  const bindings = [...view.bindings.querySelectorAll("input[data-step-id]")].map((input) => ({
    stepId: input.dataset.stepId,
    name: input.value,
  }));
  void ask("finalize-recording", { bindings }).then((answer) => {
    if (answer.saved === true) {
      void ask("connection").then(show);
    } else {
      say(answer.message ?? REFUSALS[answer.reason] ?? "The recording could not be saved.");
    }
  });
});

document.querySelector("#disconnect").addEventListener("click", () => {
  // The worker clears what it holds before it hands the site access back, and
  // handing it back restarts the worker — so the answer to this may never
  // arrive. It is not needed: the disconnection is already true by the time it
  // could have been sent, and this popup says so without being told.
  const version = view.version.textContent;
  void ask("disconnect").then(show, () => undefined);
  show({ connection: null, version });
});

// A popup is closed the moment it loses focus, and fetching a connect code from
// the app costs it exactly that — so what is typed here is handed to the worker
// as it is typed, and the popup that comes back opens where this one left off.
view.address.addEventListener("input", () => {
  void ask("remember-address", { address: view.address.value });
});

// The connection is made in a tab, so it can arrive while this popup is open.
chrome.storage.local.onChanged.addListener(() => {
  void ask("connection").then(show);
});

void ask("connection").then((state) => {
  show(state);
  view.address.value = state.address ?? "";
});

/**
 * Ask for the origin from this click, and then do whatever the button meant.
 *
 * The request is Chrome's own dialog: it either grants the origin or it does
 * not, and a decline is an answer to show rather than an error.
 */
function connect(how) {
  const read = readInstanceUrl(view.address.value);
  if (read.origin === undefined) {
    say(ADDRESS_PROBLEMS[read.problem]);
    return;
  }

  // Both calls belong to this click, and nothing is awaited between them: an
  // `await` would spend the gesture and the request would be refused without
  // ever being shown. The announcement is sent and not waited for, for that
  // reason — and it is what lets the worker finish alone if this popup is
  // closed by the dialog, which on most desktops is what happens.
  say("");
  const announced = ask("about-to-connect", { origin: read.origin, how, code: view.code.value });
  chrome.permissions
    .request({ origins: [originPattern(read.origin)] })
    .then(async (granted) => {
      if (!granted) {
        // This popup outlived the dialog, so the announcement has been answered
        // here and the next popup to open must not say this again.
        void ask("declined");
        declined();
        return undefined;
      }
      // Now the gesture is spent and waiting costs nothing. An origin already
      // granted resolves the request in this same tick, and asking to finish
      // before the announcement had landed would find nothing announced.
      await announced;
      return ask("finish-connect").then(landed);
    })
    .catch(() => say(REFUSALS.failed));
}

/** What came back from the worker, as a sentence or as a new state. */
function landed(answer) {
  if (answer.late === true) {
    // The grant finished it while this popup was still asking. What it did is
    // in the worker's storage, which is where this popup's state comes from.
    void ask("connection").then(show);
    return;
  }
  if (answer.opened === true) {
    say(`Waiting for ${short(view.address.value)} to hand the connection over…`);
    return;
  }
  if (answer.connected === true) {
    void ask("connection").then(show);
    return;
  }
  view.fallback.open = answer.reason === "bad-code" || view.fallback.open;
  say(REFUSALS[answer.reason] ?? REFUSALS.failed);
}

function show(state) {
  const connected = state.connection !== null && state.connection !== undefined;
  const recording = state.recording ?? null;
  view.connected.hidden = !connected || recording !== null;
  view.connect.hidden = connected;
  view.pending.hidden = recording?.state !== "pending";
  view.active.hidden = recording?.state !== "recording";
  view.save.hidden = recording?.state !== "ended";
  if (recording?.state === "pending") view.pendingWorkflow.textContent = recording.workflowName;
  if (recording?.state === "recording") view.activeWorkflow.textContent = recording.workflowName;
  if (recording?.state === "ended") renderSave(recording);
  view.version.textContent = state.version ?? "";
  if (connected) {
    view.instance.textContent = state.connection.origin;
    say(recording?.tokenExpired === true ? "Open this Workflow in the app to resume." : "");
    return;
  }
  if (state.unanswered === true) {
    declined();
  }
}

function startPendingRecording() {
  const tab = targetTab;
  if (typeof tab?.id !== "number" || typeof tab.url !== "string" || !/^https?:/.test(tab.url)) {
    say("Open the first web page you want to record, then try again.");
    return;
  }
  const origin = new URL(tab.url).origin;
  const announced = ask("about-to-start-recording", { targetTabId: tab.id, targetUrl: tab.url });
  chrome.permissions
    .request({ origins: [originPattern(origin)] })
    .then(async (granted) => {
      if (!granted) {
        say("Nothing was recorded because Chrome did not grant access to this site.");
        return;
      }
      await announced;
      const answer = await ask("finish-recording-start");
      if (answer.started !== true && answer.late !== true) {
        say("That tab could not be recorded. Keep it open and try again.");
      }
      show(await ask("connection"));
    })
    .catch(() => say(REFUSALS.failed));
}

function renderSave(recording) {
  view.saveWorkflow.textContent = recording.workflowName;
  view.saveSummary.textContent = `${String(recording.steps.length)} Steps captured.`;
  view.bindings.replaceChildren();
  view.secretVariables.replaceChildren();
  for (const variable of recording.variables ?? []) {
    if (variable.secret !== true) continue;
    const option = document.createElement("option");
    option.value = variable.name;
    view.secretVariables.append(option);
  }
  for (const step of recording.steps.filter((candidate) => candidate.needsSecret === true)) {
    const label = document.createElement("label");
    label.textContent = `${step.label} — secret Variable`;
    const input = document.createElement("input");
    input.dataset.stepId = step.id;
    input.setAttribute("list", "secret-variables");
    input.placeholder = "password";
    input.autocomplete = "off";
    label.append(input);
    view.bindings.append(label);
  }
}

/** Say what a refused permission means, and offer the way in that is left. */
function declined() {
  view.fallback.open = true;
  say(DECLINED);
}

function ask(type, payload = {}) {
  return chrome.runtime.sendMessage({ type, ...payload });
}

function say(sentence) {
  view.note.textContent = sentence;
}

/** The address as typed, trimmed to something a sentence can carry. */
function short(typed) {
  const read = readInstanceUrl(typed);
  return read.origin ?? typed.trim();
}
