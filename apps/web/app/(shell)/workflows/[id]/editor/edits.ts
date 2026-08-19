import type { WorkflowDocument } from "@step-by-step/api-client";

import type { Step } from "./steps";

/**
 * Every edit the card list makes, as a document in and a document out.
 *
 * A save replaces the Draft whole, so the editor holds one document and each
 * tool hands back the next one. Nothing here reaches into a Step to renumber
 * it: an id is minted when the Step is created — at capture, or by the add
 * menu — and every edit after that carries it across, which is what lets a
 * Step keep its Step Results and its Selector Drift across Versions.
 */

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
