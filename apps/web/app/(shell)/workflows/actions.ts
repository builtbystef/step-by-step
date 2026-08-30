import type { DraftState } from "@step-by-step/api-client";

import { refusalToRun } from "./draft-state";

export type WorkflowAction = {
  key: string;
  label: string;
  needsAVersion: boolean;
  destructive?: boolean;
};

export const RUN: WorkflowAction = { key: "run", label: "Run", needsAVersion: true };

export const NEW_BATCH: WorkflowAction = {
  key: "new-batch",
  label: "New batch",
  needsAVersion: true,
};
export const NEW_SCHEDULE: WorkflowAction = {
  key: "new-schedule",
  label: "New schedule",
  needsAVersion: true,
};

export const OVERFLOW_ACTIONS: readonly WorkflowAction[] = [
  NEW_BATCH,
  NEW_SCHEDULE,
  { key: "duplicate", label: "Duplicate", needsAVersion: false },
  { key: "rename", label: "Rename", needsAVersion: false },
  { key: "delete", label: "Delete", needsAVersion: false, destructive: true },
];

export function disabledReason(action: WorkflowAction, state: DraftState): string | null {
  return action.needsAVersion ? refusalToRun(state) : null;
}
