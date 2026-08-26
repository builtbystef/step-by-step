import type { CreateBatch } from "@step-by-step/api-client";

import {
  submittedVariables,
  type GridColumn,
  type GridRow,
} from "../../../../../../components/value-grid/grid";
import { duration } from "../../../../../../lib/duration";

/**
 * The Batch creation page's decisions: the default name, the copy-from name,
 * the incomplete-row flag on the payload, the sequential ETA, and where
 * submit navigates.
 */

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
  return `${workflowName} — ${calendarDate(now)}`;
}

export function rerunBatchName(workflowName: string, batchName: string): string {
  return `${workflowName} — rerun of ${batchName}`;
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
