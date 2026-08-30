import type { WorkflowDocument } from "@step-by-step/api-client";

import type { Step } from "./steps";

export type Direction = "up" | "down";

function stepsOf(document: WorkflowDocument): Step[] {
  return document.steps ?? [];
}

export function withStepMoved(
  document: WorkflowDocument,
  id: string,
  direction: Direction,
): WorkflowDocument {
  const steps = stepsOf(document);
  const at = steps.findIndex((step) => step.id === id);
  const to = direction === "up" ? at - 1 : at + 1;
  const moving = steps[at];
  const displaced = steps[to];
  if (moving === undefined || displaced === undefined) {
    return document;
  }
  const reordered = [...steps];
  reordered[at] = displaced;
  reordered[to] = moving;
  return { ...document, steps: reordered };
}

export function withStepDeleted(document: WorkflowDocument, id: string): WorkflowDocument {
  return { ...document, steps: stepsOf(document).filter((step) => step.id !== id) };
}

export function withStepAdded(document: WorkflowDocument, step: Step): WorkflowDocument {
  return { ...document, steps: [...stepsOf(document), step] };
}

export function withStepReplaced(document: WorkflowDocument, step: Step): WorkflowDocument {
  return {
    ...document,
    steps: stepsOf(document).map((existing) => (existing.id === step.id ? step : existing)),
  };
}
