import type { Target, WorkflowDocument } from "@step-by-step/api-client";

export type Step = NonNullable<WorkflowDocument["steps"]>[number];
export type StepType = Step["type"];

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

function emptyTarget(): Target {
  return { candidates: [] };
}

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

export function withWaitMode(step: Step, mode: "duration" | "element"): Step {
  if (step.type !== "wait" || step.payload.mode === mode) {
    return step;
  }
  if (mode === "element") {
    return { ...step, payload: { mode: "element", target: emptyTarget() } };
  }
  return { ...step, payload: { mode: "duration", durationMs: DEFAULT_WAIT_MS } };
}

export function interpolatedValue(step: Step): string | null {
  if (step.type === "navigate") {
    return step.payload.url;
  }
  return step.type === "type" ? step.payload.value : null;
}

export function withInterpolatedValue(step: Step, value: string): Step {
  if (step.type === "navigate") {
    return { ...step, payload: { ...step.payload, url: value } };
  }
  if (step.type === "type") {
    return { ...step, payload: { ...step.payload, value } };
  }
  return step;
}
