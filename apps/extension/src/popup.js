/**
 * The popup: the one surface where a person connects this extension to their
 * instance, and the only place a permission can be asked for.
 *
 * Chrome grants an optional host permission only from a user gesture, so
 * `chrome.permissions.request` is called from the click itself, before
 * anything is awaited — an `await` first would spend the gesture and the
 * request would be refused without ever being shown.
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
};

document.querySelector("#connect-button").addEventListener("click", () => {
  connect((origin) => ask("connect-through-the-page", { origin }));
});

document.querySelector("#code-button").addEventListener("click", () => {
  connect((origin) => ask("connect-with-code", { origin, code: view.code.value }));
});

document.querySelector("#disconnect").addEventListener("click", () => {
  void ask("disconnect").then(show);
});

// The connection is made in a tab, so it can arrive while this popup is open.
chrome.storage.local.onChanged.addListener(() => {
  void ask("connection").then(show);
});

void ask("connection").then(show);

/**
 * Ask for the origin from this click, and then do whatever the button meant.
 *
 * The request is Chrome's own dialog: it either grants the origin or it does
 * not, and a decline is an answer to show rather than an error.
 */
function connect(act) {
  const read = readInstanceUrl(view.address.value);
  if (read.origin === undefined) {
    say(ADDRESS_PROBLEMS[read.problem]);
    return;
  }

  say("");
  chrome.permissions
    .request({ origins: [originPattern(read.origin)] })
    .then((granted) => {
      if (!granted) {
        view.fallback.open = true;
        say(
          "Step by Step needs Chrome's permission for that address before it can connect. " +
            "Try again, and choose Allow.",
        );
        return undefined;
      }
      return act(read.origin).then(landed);
    })
    .catch(() => say(REFUSALS.failed));
}

/** What came back from the worker, as a sentence or as a new state. */
function landed(answer) {
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
  view.connected.hidden = !connected;
  view.connect.hidden = connected;
  view.version.textContent = state.version ?? "";
  if (connected) {
    view.instance.textContent = state.connection.origin;
    say("");
  }
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
