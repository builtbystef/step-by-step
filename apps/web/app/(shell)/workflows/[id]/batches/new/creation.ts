import type { CreateBatch, Variable } from "@step-by-step/api-client";

import {
  submittedVariables,
  type GridColumn,
  type GridRow,
} from "../../../../../../components/value-grid/grid";
import { duration } from "../../../../../../lib/duration";

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
] as const;

export function defaultBatchName(workflowName: string, now: Date): string {
  return `${workflowName} · ${calendarDate(now)}`;
}

export function rerunBatchName(workflowName: string, batchName: string): string {
  return `${workflowName} · rerun of ${batchName}`;
}

export function sequentialEta(rowCount: number, medianMs: number | null | undefined): string {
  if (medianMs === null || medianMs === undefined) {
    return `${String(rowCount)} Runs, one at a time`;
  }
  return `about ${duration(medianMs * rowCount)}`;
}

export function progressHref(batchId: string): string {
  return `/batches/${batchId}`;
}

export function createBody(
  name: string,
  rows: readonly GridRow[],
  columns: readonly GridColumn[],
  runIncompleteRows: boolean,
): CreateBatch {
  return {
    name,
    run_incomplete_rows: runIncompleteRows,
    rows: rows.map((row) => ({ variables: submittedVariables(row, columns) })),
  };
}

function calendarDate(now: Date): string {
  return `${String(now.getDate())} ${MONTHS[now.getMonth()] ?? ""} ${String(now.getFullYear())}`;
}

export function addedVariables(
  baselineNames: readonly string[],
  latest: readonly Variable[],
): Variable[] {
  const known = new Set(baselineNames);
  return latest.filter((variable) => variable.secret !== true && !known.has(variable.name));
}

export function mergeVariables(
  current: readonly Variable[],
  added: readonly Variable[],
): Variable[] {
  const names = new Set(current.map((variable) => variable.name));
  return [...current, ...added.filter((variable) => !names.has(variable.name))];
}

export type CreationDriftBanner = {
  name: string;
  title: string;
  offer: string;
};

export function creationDriftBanner(added: readonly Variable[]): CreationDriftBanner | null {
  const first = added[0];
  if (first === undefined) {
    return null;
  }
  return {
    name: first.name,
    title: `This Workflow now needs ${first.name}`,
    offer: "Give every row the same value",
  };
}

export function submitBlockedByDrift(added: readonly Variable[]): boolean {
  return added.length > 0;
}
