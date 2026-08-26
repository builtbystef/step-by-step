import type { BatchRowRecord, BatchStats, RunStatus } from "@step-by-step/api-client";

import { duration } from "../../../../lib/duration";
import type { LifecycleState } from "@/lib/labels";

/**
 * The batch view's decisions, kept out of the JSX so a test can read the
 * acceptance criteria back: the stats header, the segmented bar, the live
 * badge, the ETA, row expansion copy, the stalled callout, and Output-tab
 * download URLs.
 *
 * Lifecycle state is named here only as a value handed to `StatusChip`.
 * This module never words a state itself.
 */

export type StatsView = {
  done: number;
  total: number;
  succeeded: number;
  failed: number;
  queued: number;
  skipped: number;
};

const SKIPPED_LIKE: ReadonlySet<BatchRowRecord["status"]> = new Set(["skipped", "cancelled"]);

export function statsView(rows: BatchRowRecord[]): StatsView {
  let succeeded = 0;
  let failed = 0;
  let queued = 0;
  let skipped = 0;
  for (const row of rows) {
    if (row.status === "succeeded") succeeded += 1;
    else if (row.status === "failed") failed += 1;
    else if (row.status === "queued") queued += 1;
    else if (SKIPPED_LIKE.has(row.status)) skipped += 1;
  }
  return {
    done: succeeded + failed,
    total: rows.length,
    succeeded,
    failed,
    queued,
    skipped,
  };
}

export type ProgressTone = "ok" | "bad" | "accent" | "neutral" | "muted";

export type ProgressSegment = {
  key: "succeeded" | "failed" | "running" | "skipped" | "queued";
  count: number;
  tone: ProgressTone;
};

export function progressSegments(stats: BatchStats): ProgressSegment[] {
  return [
    { key: "succeeded", count: stats.succeeded, tone: "ok" },
    { key: "failed", count: stats.failed, tone: "bad" },
    { key: "running", count: stats.running, tone: "accent" },
    { key: "skipped", count: stats.skipped + stats.cancelled, tone: "neutral" },
    { key: "queued", count: stats.queued, tone: "muted" },
  ];
}

export function liveRowIndex(rows: BatchRowRecord[]): number | null {
  const index = rows.findIndex((row) => row.status === "running");
  return index === -1 ? null : index;
}

export function etaLabel(seconds: number | null | undefined): string | null {
  if (seconds === null || seconds === undefined) {
    return null;
  }
  return `${duration(seconds * 1000)} left`;
}

export function rowChipState(
  row: BatchRowRecord,
  liveRunStatus?: RunStatus | null,
): LifecycleState {
  if (liveRunStatus === "waiting_for_human") {
    return "waiting_for_human";
  }
  return row.status;
}

export function rowDurationMs(row: BatchRowRecord, now: Date): number | null {
  const latest = row.runs[row.runs.length - 1];
  if (latest === undefined || latest.started_at === null) {
    return null;
  }
  const end = latest.ended_at === null ? now.getTime() : Date.parse(latest.ended_at);
  return Math.max(0, end - Date.parse(latest.started_at));
}

export function variableColumns(rows: BatchRowRecord[]): string[] {
  const columns: string[] = [];
  const seen = new Set<string>();
  for (const row of rows) {
    for (const key of Object.keys(row.variables)) {
      if (!seen.has(key)) {
        seen.add(key);
        columns.push(key);
      }
    }
  }
  return columns;
}

export function runHref(runId: string): string {
  return `/runs/${runId}`;
}

const FAILURE_WORDS: Record<string, string> = {
  step_failed: "A Step failed — a selector missed, an action errored, or the Step timed out.",
  takeover_timeout: "The waiting-for-you deadline passed.",
  auth_challenge: "A Step failed while an authentication challenge was on the page.",
  takeover_abandoned: "Control was abandoned.",
  run_timeout: "The Run timed out.",
  worker_lost: "The Worker was lost.",
  missing_secret: "A Secret this Workflow needs is missing.",
  startup_failed: "The Run failed to start.",
};

export function failureReasonWords(reason: string | null): string {
  if (reason === null) {
    return "This row failed.";
  }
  return FAILURE_WORDS[reason] ?? "This row failed.";
}

export type StalledInput = {
  rowIndex: number;
  queuedCount: number;
  deadlineAt: string;
  now: Date;
};

export type StalledCallout = {
  title: string;
  sequential: string;
  timeout: string;
  countdown: string;
  takeOver: string;
  skip: string;
};

export function takeOverLabel(displayRow: number): string {
  return `Take over row ${String(displayRow)}`;
}

export function stalledCallout(input: StalledInput | null): StalledCallout | null {
  if (input === null) {
    return null;
  }
  const display = input.rowIndex + 1;
  return {
    title: `Row ${String(display)} is waiting for you`,
    sequential: `Rows run one at a time — the other ${String(input.queuedCount)} rows stay queued until this one is dealt with.`,
    timeout: "If the deadline passes, this row fails and the Batch moves on.",
    countdown: countdownLabel(input.deadlineAt, input.now),
    takeOver: takeOverLabel(display),
    skip: "Skip this row",
  };
}

function countdownLabel(deadlineAt: string, now: Date): string {
  const remaining = Math.max(0, Math.floor((Date.parse(deadlineAt) - now.getTime()) / 1000));
  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;
  return `${String(minutes)}:${String(seconds).padStart(2, "0")} left`;
}

export function outputDownloadHref(batchId: string, format: "json" | "csv"): string {
  return `/api/batches/${batchId}/output?format=${format}`;
}

export type OutputTable = {
  columns: string[];
  rows: string[][];
};

export function batchOutputTable(assembled: unknown): OutputTable | null {
  if (!isPlainObject(assembled)) {
    return null;
  }
  const columns = assembled.columns;
  const rows = assembled.rows;
  if (!Array.isArray(columns) || !columns.every((column) => typeof column === "string")) {
    return null;
  }
  if (!Array.isArray(rows)) {
    return null;
  }
  if (columns.length === 0) {
    return null;
  }
  return {
    columns,
    rows: rows.map((row) => {
      const cells = Array.isArray(row) ? row : [];
      return columns.map((_, index) => cellOf(cells[index]));
    }),
  };
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function cellOf(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

export function variableCell(value: unknown): string {
  return cellOf(value);
}
