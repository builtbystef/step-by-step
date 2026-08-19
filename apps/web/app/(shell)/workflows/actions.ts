import type { DraftState } from "@step-by-step/api-client";

import { refusalToRun } from "./draft-state";

/**
 * What can be done to a Workflow without opening it.
 *
 * One list, because the list row's hover menu and the Workflow header's
 * overflow offer the same things — a row and a header that drifted apart
 * would make where you are change what you can do.
 */

export type WorkflowAction = {
  key: string;
  label: string;
  /** Acts on a published Version, so a Workflow without one cannot use it. */
  needsAVersion: boolean;
  /** Ends the Workflow, so it is rendered apart from the rest. */
  destructive?: boolean;
};

/** The one action that is not in the overflow: it is the row's own button. */
export const RUN: WorkflowAction = { key: "run", label: "Run", needsAVersion: true };

export const OVERFLOW_ACTIONS: readonly WorkflowAction[] = [
  { key: "new-batch", label: "New batch", needsAVersion: true },
  { key: "new-schedule", label: "New schedule", needsAVersion: true },
  { key: "duplicate", label: "Duplicate", needsAVersion: false },
  { key: "rename", label: "Rename", needsAVersion: false },
  { key: "delete", label: "Delete", needsAVersion: false, destructive: true },
];

/**
 * Why this action is disabled on this Workflow, or nothing when it is not.
 *
 * The three that start something are disabled together and behind one
 * sentence; housekeeping is left alone, because a Workflow nobody ever
 * published is exactly the one somebody wants to rename or throw away.
 */
export function disabledReason(action: WorkflowAction, state: DraftState): string | null {
  return action.needsAVersion ? refusalToRun(state) : null;
}
