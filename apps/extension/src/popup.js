import { originPattern, readInstanceUrl } from "./lib/instance.js";
import { replacementHint, sitePattern } from "./lib/recording.js";

const ADDRESS_PROBLEMS = {
  empty: "Enter the address of your Step by Step instance.",
  malformed: "That does not look like a web address.",
  "unsupported-scheme": "An instance is reached over http or https.",
};

const DECLINED =
  "Step by Step needs Chrome's permission for that address before it can connect. " +
  "Try again, and choose Allow.";

const REFUSALS = {
  "not-permitted": "Chrome did not allow this extension to work on that address.",
  "instance-tab":
    "This is the Step by Step tab. Open the first page of the task in another tab, " +
    "then start recording from there.",
  "target-gone": "That tab could not be recorded. Keep it open and try again.",
  "login-not-permitted":
    "Nothing was saved. Copying a login needs Chrome's permission for the whole site. " +
    "Save again, and choose Allow.",
  "not-an-instance": "That does not look like a web address.",
  "bad-code": "That code is not valid any more. Show a new one in the app.",
  unreachable: "That address did not answer. Check it, and that the instance is running.",
  failed: "Something went wrong. Try again.",
};

// What the pill in the popup's header says, for each state the popup can be in.
const STATUS = {
  disconnected: { label: "Not connected", tone: "neutral", live: false },
  connected: { label: "Connected", tone: "ok", live: false },
  pending: { label: "Ready", tone: "wait", live: false },
  recording: { label: "Recording", tone: "accent", live: true },
  ended: { label: "Needs review", tone: "wait", live: false },
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
  status: document.querySelector("#status"),
  statusDot: document.querySelector("#status .dot"),
  statusLabel: document.querySelector("#status-label"),
  pending: document.querySelector("#recording-pending"),
  pendingWorkflow: document.querySelector("#pending-workflow"),
  pendingVerb: document.querySelector("#pending-verb"),
  pendingHint: document.querySelector("#pending-hint"),
  recordButton: document.querySelector("#record-button"),
  active: document.querySelector("#recording-active"),
  activeVerb: document.querySelector("#active-verb"),
  activeWorkflow: document.querySelector("#active-workflow"),
  activeHint: document.querySelector("#active-hint"),
  stopButton: document.querySelector("#stop-button"),
  save: document.querySelector("#recording-save"),
  saveWorkflow: document.querySelector("#save-workflow"),
  saveSummary: document.querySelector("#save-summary"),
  bindings: document.querySelector("#secret-bindings"),
  secretVariables: document.querySelector("#secret-variables"),
  authChoices: document.querySelector("#auth-state-choices"),
};

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
  const bindings = [...view.bindings.querySelectorAll("[data-step-id]")].map((row) => {
    const choice = row.querySelector("select[data-secret-choice]");
    const selected = choice.selectedOptions[0];
    const common = {
      stepId: row.dataset.stepId,
      name: row.querySelector("input[data-variable-name]").value,
    };
    if (choice.value === "new") {
      return {
        ...common,
        create: {
          name: row.querySelector("input[data-secret-name]").value,
          value: row.querySelector("input[data-secret-value]").value,
        },
      };
    }
    return {
      ...common,
      ...(choice.value
        ? { secret: { id: choice.value, name: selected?.dataset.secretName ?? "" } }
        : {}),
    };
  });
  const authSelections = [...view.authChoices.querySelectorAll("[data-auth-domain]")].map(
    (row) => ({
      domain: row.dataset.authDomain,
      checked: row.querySelector('input[type="checkbox"]').checked,
      scope: row.querySelector("select").value,
    }),
  );
  const sites = authSelections
    .filter((choice) => choice.checked === true)
    .map((choice) => sitePattern(choice.domain));
  // Asked before an await consumes the user gesture, and asked at all because
  // Chrome shows a site's cookies only to an extension permitted across that site.
  const permitted =
    sites.length === 0 ? Promise.resolve(true) : chrome.permissions.request({ origins: sites });
  void permitted
    .then((granted) => {
      if (!granted) {
        say(REFUSALS["login-not-permitted"], "bad");
        return;
      }
      void ask("finalize-recording", { bindings, authSelections }).then((answer) => {
        if (answer.saved === true) {
          void ask("connection").then(show);
        } else {
          say(
            answer.message ?? REFUSALS[answer.reason] ?? "The recording could not be saved.",
            "bad",
          );
        }
      });
    })
    .catch(() => say(REFUSALS.failed, "bad"));
});

document.querySelector("#disconnect").addEventListener("click", () => {
  const version = view.version.textContent;
  void ask("disconnect").then(show, () => undefined);
  show({ connection: null, version });
});

view.address.addEventListener("input", () => {
  void ask("remember-address", { address: view.address.value });
});

chrome.storage.local.onChanged.addListener(() => {
  void ask("connection").then(show);
});

void ask("connection").then((state) => {
  show(state);
  view.address.value = state.address ?? "";
});

function connect(how) {
  const read = readInstanceUrl(view.address.value);
  if (read.origin === undefined) {
    say(ADDRESS_PROBLEMS[read.problem], "bad");
    return;
  }

  say("");
  const announced = ask("about-to-connect", { origin: read.origin, how, code: view.code.value });
  // Request permission before an await consumes the user gesture.
  chrome.permissions
    .request({ origins: [originPattern(read.origin)] })
    .then(async (granted) => {
      if (!granted) {
        void ask("declined");
        declined();
        return undefined;
      }
      await announced;
      return ask("finish-connect").then(landed);
    })
    .catch(() => say(REFUSALS.failed, "bad"));
}

function landed(answer) {
  if (answer.late === true) {
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
  say(REFUSALS[answer.reason] ?? REFUSALS.failed, "bad");
}

function show(state) {
  const connected = state.connection !== null && state.connection !== undefined;
  const recording = state.recording ?? null;
  view.connected.hidden = !connected || recording !== null;
  view.connect.hidden = connected;
  view.pending.hidden = recording?.state !== "pending";
  view.active.hidden = recording?.state !== "recording";
  view.save.hidden = recording?.state !== "ended";
  wear(recording?.state ?? (connected ? "connected" : "disconnected"));
  const repick = recording?.mode === "repick";
  if (recording?.state === "pending") {
    view.pendingWorkflow.textContent = recording.workflowName;
    view.pendingVerb.textContent = repick ? "Ready to re-pick" : "Ready to record";
    view.pendingHint.textContent = repick
      ? "Open the page that has the element in this window, then confirm here."
      : "Open the first page of the task in this window, then confirm here.";
    view.recordButton.textContent = repick
      ? "Pick an element in this tab"
      : "Start recording this tab";
  }
  if (recording?.state === "recording") {
    view.activeVerb.textContent = repick ? "Pick an element on" : "Recording";
    view.activeWorkflow.textContent = recording.workflowName;
    view.activeHint.textContent = repick
      ? "The editor will show the new selectors beside the old ones."
      : "Complete the task in this tab, then stop to review every Step.";
    view.stopButton.textContent = repick ? "Cancel" : "Stop and review";
  }
  if (recording?.state === "ended") renderSave(recording);
  view.version.textContent = state.version ?? "";
  if (connected) {
    view.instance.textContent = state.connection.origin;
    say(recording?.tokenExpired === true ? "Open this Workflow in the app to resume." : "", "wait");
    return;
  }
  if (state.unanswered === true) {
    declined();
  }
}

function wear(state) {
  const badge = STATUS[state];
  view.status.hidden = badge === undefined;
  if (badge === undefined) return;
  view.status.dataset.tone = badge.tone;
  view.statusDot.dataset.live = String(badge.live);
  view.statusLabel.textContent = badge.label;
}

function startPendingRecording() {
  const tab = targetTab;
  if (typeof tab?.id !== "number" || typeof tab.url !== "string" || !/^https?:/.test(tab.url)) {
    say("Open the first web page you want to record, then try again.", "wait");
    return;
  }
  const origin = new URL(tab.url).origin;
  const announced = ask("about-to-start-recording", { targetTabId: tab.id, targetUrl: tab.url });
  chrome.permissions
    .request({ origins: [originPattern(origin)] })
    .then(async (granted) => {
      if (!granted) {
        say("Nothing was recorded because Chrome did not grant access to this site.", "bad");
        return;
      }
      await announced;
      const answer = await ask("finish-recording-start");
      if (answer.started !== true && answer.late !== true) {
        say(REFUSALS[answer.reason] ?? REFUSALS["target-gone"], "bad");
      }
      show(await ask("connection"));
    })
    .catch(() => say(REFUSALS.failed, "bad"));
}

function renderSave(recording) {
  view.saveWorkflow.textContent = recording.workflowName;
  view.saveSummary.textContent = `${String(recording.steps.length)} Steps captured.`;
  view.bindings.replaceChildren();
  view.authChoices.replaceChildren();
  view.secretVariables.replaceChildren();
  for (const variable of recording.variables ?? []) {
    if (variable.secret !== true) continue;
    const option = document.createElement("option");
    option.value = variable.name;
    view.secretVariables.append(option);
  }
  for (const choice of recording.authChoices ?? []) {
    const row = document.createElement("div");
    row.dataset.authDomain = choice.domain;
    row.className = "auth-state-choice";
    const consent = document.createElement("label");
    consent.className = "consent";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    consent.append(
      checkbox,
      ` Save your login for ${choice.domain}? Future runs will start already signed in.`,
    );
    const destination = document.createElement("select");
    destination.hidden = true;
    destination.append(new Option("for the Organization", "organization"));
    destination.append(new Option("just for me", "personal"));
    const hint = document.createElement("span");
    hint.className = "quiet";
    const update = () => {
      destination.hidden = !checkbox.checked;
      hint.textContent = checkbox.checked ? replacementHint(choice, destination.value) : "";
    };
    checkbox.addEventListener("change", update);
    destination.addEventListener("change", update);
    row.append(consent, destination, hint);
    view.authChoices.append(row);
  }
  for (const step of recording.steps.filter((candidate) => candidate.needsSecret === true)) {
    const row = document.createElement("div");
    row.className = "secret-binding";
    row.dataset.stepId = step.id;

    const heading = document.createElement("p");
    heading.className = "label";
    heading.textContent = step.label;

    const variableLabel = document.createElement("label");
    variableLabel.textContent = "Variable name";
    const variable = document.createElement("input");
    variable.dataset.variableName = "";
    variable.setAttribute("list", "secret-variables");
    variable.placeholder = "password";
    variable.autocomplete = "off";
    variableLabel.append(variable);

    const secretLabel = document.createElement("label");
    secretLabel.textContent = "Secret";
    const choice = document.createElement("select");
    choice.dataset.secretChoice = "";
    choice.append(new Option("Choose a Secret", ""));
    for (const secret of recording.secrets ?? []) {
      const option = new Option(secret.name, secret.id);
      option.dataset.secretName = secret.name;
      choice.append(option);
    }
    choice.append(new Option("Create a new Secret", "new"));
    secretLabel.append(choice);

    const create = document.createElement("div");
    create.className = "secret-create";
    create.hidden = true;
    const nameLabel = document.createElement("label");
    nameLabel.textContent = "New Secret name";
    const name = document.createElement("input");
    name.dataset.secretName = "";
    name.autocomplete = "off";
    nameLabel.append(name);
    const valueLabel = document.createElement("label");
    valueLabel.textContent = "Value";
    const value = document.createElement("input");
    value.type = "password";
    value.dataset.secretValue = "";
    value.autocomplete = "new-password";
    valueLabel.append(value);
    create.append(nameLabel, valueLabel);
    choice.addEventListener("change", () => {
      create.hidden = choice.value !== "new";
    });

    row.append(heading, variableLabel, secretLabel, create);
    view.bindings.append(row);
  }
}

function declined() {
  view.fallback.open = true;
  say(DECLINED, "wait");
}

function ask(type, payload = {}) {
  return chrome.runtime.sendMessage({ type, ...payload });
}

// The one sentence the popup says back, in the tone the app gives that meaning.
function say(sentence, tone = "info") {
  view.note.textContent = sentence;
  view.note.dataset.tone = tone;
}

function short(typed) {
  const read = readInstanceUrl(typed);
  return read.origin ?? typed.trim();
}
