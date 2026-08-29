import type { Target, WorkflowDocument } from "@step-by-step/api-client";

/**
 * What a Step is, as far as the editor is concerned.
 *
 * The document's shape is the backend's — the generated client hands it over
 * as a union discriminated by `type`, so a card that reads a payload has
 * already been told which of the eight it is holding. What is here is what
 * the shape does not say: what each type is called in front of a person,
 * where a Step keeps the elements it points at, and what a Step a person
 * added by hand starts out as.
 */

export type Step = NonNullable<WorkflowDocument["steps"]>[number];
export type StepType = Step["type"];

/** What each type is called on a card and in the add menu. */
export const STEP_TYPE_LABELS: Record<StepType, string> = {
  navigate: "Go to a page",
  click: "Click",
  type: "Type",
  select: "Choose from a list",
  download: "Download a file",
  extract: "Extract a value",
  wait: "Wait",
  "pause-for-takeover": "Pause for a person",
};

/**
 * Every element this Step has to find on the page.
 *
 * Usually one and sometimes none, and a pause has one when it knows what the
 * person finishing it leaves behind. Selector health reads all of them,
 * because a Step is only as findable as its least findable target.
 */
export function targetsOf(step: Step): Target[] {
  if (step.type === "wait") {
    return step.payload.mode === "element" ? [step.payload.target] : [];
  }
  if (step.type === "pause-for-takeover") {
    return step.payload.successCheck ? [step.payload.successCheck] : [];
  }
  if (step.type === "navigate") {
    return [];
  }
  return [step.payload.target];
}

/**
 * The types a person adds in the editor: all eight.
 *
 * A targeting Step arrives with an empty candidate list. The selector panel
 * is how that list gets filled — by hand, or by Re-pick — so minting one
 * here is finishable. Wait still starts as a duration; switching it to wait
 * for an element lands on the same empty target.
 */
export const ADDABLE_STEP_TYPES = [
  "navigate",
  "click",
  "type",
  "select",
  "download",
  "extract",
  "wait",
  "pause-for-takeover",
] as const satisfies readonly StepType[];

export type AddableStepType = (typeof ADDABLE_STEP_TYPES)[number];

const DEFAULT_WAIT_MS = 1000;

/** A target nobody has pointed at yet — the selector panel is how it fills. */
function emptyTarget(): Target {
  return { candidates: [] };
}

/**
 * A new Step, under an id of its own.
 *
 * The id is minted here and never rewritten afterwards: it is the thread that
 * ties this Step to its Step Results and its Selector Drift across every
 * Version it goes on to appear in.
 */
export function blankStep(type: AddableStepType): Step {
  const envelope = {
    id: crypto.randomUUID(),
    optional: false,
    disabled: false,
    label: STEP_TYPE_LABELS[type],
  };
  switch (type) {
    case "navigate":
      return { ...envelope, type, payload: { url: "" } };
    case "click":
      return { ...envelope, type, payload: { target: emptyTarget() } };
    case "type":
      return { ...envelope, type, payload: { target: emptyTarget(), value: "" } };
    case "select":
      return { ...envelope, type, payload: { target: emptyTarget(), value: "" } };
    case "download":
      return { ...envelope, type, payload: { target: emptyTarget() } };
    case "extract":
      return {
        ...envelope,
        type,
        payload: { target: emptyTarget(), outputName: "", mode: "scalar" },
      };
    case "wait":
      return {
        ...envelope,
        type,
        payload: { mode: "duration", durationMs: DEFAULT_WAIT_MS },
      };
    case "pause-for-takeover":
      return { ...envelope, type, payload: {} };
  }
}

/**
 * The same wait, as the other of its two modes.
 *
 * Switching to an element lands on an empty candidate list — the same target
 * a hand-added click arrives with, so the selector panel is how it is filled.
 * Switching back to a duration drops the target and starts a one-second pause.
 * A wait already in that mode is handed back as it is.
 */
export function withWaitMode(step: Step, mode: "duration" | "element"): Step {
  if (step.type !== "wait" || step.payload.mode === mode) {
    return step;
  }
  if (mode === "element") {
    return { ...step, payload: { mode: "element", target: emptyTarget() } };
  }
  return { ...step, payload: { mode: "duration", durationMs: DEFAULT_WAIT_MS } };
}

/**
 * The one value this Step interpolates Variables into, or null.
 *
 * A navigate URL and a type value are the two, and they are the two the
 * document store interpolates as well — a `{{` anywhere else is text the page
 * receives, so a Variable control has no business over that field.
 */
export function interpolatedValue(step: Step): string | null {
  if (step.type === "navigate") {
    return step.payload.url;
  }
  return step.type === "type" ? step.payload.value : null;
}

/** The same Step, with that value rewritten. Anything else is handed back as it is. */
export function withInterpolatedValue(step: Step, value: string): Step {
  if (step.type === "navigate") {
    return { ...step, payload: { ...step.payload, url: value } };
  }
  if (step.type === "type") {
    return { ...step, payload: { ...step.payload, value } };
  }
  return step;
}
