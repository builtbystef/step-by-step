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
 * The types a person adds in the editor: the ones that point at nothing.
 *
 * Wait and pause-for-takeover enter a Workflow no other way — nobody records
 * waiting — and a navigate is a URL a person can type. The five that need an
 * element need a recorded candidate list to find it with, and minting one
 * here would be a Step the editor cannot finish: the repair paths that give a
 * target its candidates are `m6s5me`'s.
 */
export const ADDABLE_STEP_TYPES = ["navigate", "wait", "pause-for-takeover"] as const;

export type AddableStepType = (typeof ADDABLE_STEP_TYPES)[number];

/**
 * A new Step, under an id of its own.
 *
 * The id is minted here and never rewritten afterwards: it is the thread that
 * ties this Step to its Step Results and its Selector Drift across every
 * Version it goes on to appear in.
 */
export function blankStep(type: AddableStepType): Step {
  const envelope = { id: crypto.randomUUID(), optional: false, disabled: false };
  if (type === "navigate") {
    return { ...envelope, type, label: "Go to a page", payload: { url: "" } };
  }
  if (type === "wait") {
    return {
      ...envelope,
      type,
      label: "Wait",
      payload: { mode: "duration", durationMs: 1000 },
    };
  }
  return { ...envelope, type, label: "Pause for a person", payload: {} };
}
