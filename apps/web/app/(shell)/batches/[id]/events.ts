import type {
  AttemptRecord,
  BatchDetail,
  BatchRecord,
  BatchRowRecord,
  BatchRowStatus,
  BatchStats,
  RunStatus,
} from "@step-by-step/api-client";

/**
 * How a live Batch advances without a reload.
 *
 * Reconnection still refetches over REST — this reducer only applies
 * `batch.row` events that arrived after the last fetch. Commands never
 * travel on this path.
 */

export type BatchSnapshot = {
  batch: BatchRecord;
  rows: BatchRowRecord[];
  stats: BatchStats;
  etaSeconds: number | null;
};

export type BatchEvent = {
  type: string;
  data: Record<string, unknown>;
};

export function snapshotFromDetail(detail: BatchDetail): BatchSnapshot {
  return {
    batch: detail.batch,
    rows: detail.rows,
    stats: detail.stats,
    etaSeconds: detail.eta_seconds ?? null,
  };
}

export function applyBatchEvent(state: BatchSnapshot, event: BatchEvent): BatchSnapshot {
  if (event.type !== "batch.row") {
    return state;
  }
  const index = numberOf(event.data.row_index);
  const status = statusOf(event.data.status);
  if (status === null || index < 0 || index >= state.rows.length) {
    return state;
  }
  const at = stringOf(event.data.at);
  const runId = typeof event.data.run_id === "string" ? event.data.run_id : null;
  const rows = state.rows.map((row, rowIndex) => {
    if (rowIndex !== index) {
      return row;
    }
    return applyRow(row, status, runId, at);
  });
  return {
    ...state,
    rows,
    stats: statsFromRows(rows),
  };
}

function applyRow(
  row: BatchRowRecord,
  status: BatchRowStatus,
  runId: string | null,
  at: string,
): BatchRowRecord {
  if (runId === null) {
    return { ...row, status };
  }
  const existing = row.runs.findIndex((attempt) => attempt.id === runId);
  const nextAttempt = attemptFrom(runId, status, at, existing === -1 ? null : row.runs[existing]!);
  const runs =
    existing === -1
      ? [...row.runs, nextAttempt]
      : row.runs.map((attempt, attemptIndex) =>
          attemptIndex === existing ? nextAttempt : attempt,
        );
  return {
    ...row,
    status,
    latest_run_id: runId,
    runs,
  };
}

function attemptFrom(
  id: string,
  rowStatus: BatchRowStatus,
  at: string,
  previous: AttemptRecord | null,
): AttemptRecord {
  const runStatus = runStatusOf(rowStatus);
  const terminal = runStatus === "succeeded" || runStatus === "failed" || runStatus === "cancelled";
  return {
    id,
    status: runStatus,
    failure_reason: previous?.failure_reason ?? null,
    queued_at: previous?.queued_at ?? at,
    started_at: previous?.started_at ?? (rowStatus === "queued" ? null : at),
    ended_at: terminal ? (previous?.ended_at ?? at) : null,
  };
}

function runStatusOf(status: BatchRowStatus): RunStatus {
  if (status === "skipped" || status === "cancelled") {
    return "cancelled";
  }
  return status;
}

function statsFromRows(rows: BatchRowRecord[]): BatchStats {
  const stats: BatchStats = {
    queued: 0,
    running: 0,
    succeeded: 0,
    failed: 0,
    skipped: 0,
    cancelled: 0,
  };
  for (const row of rows) {
    stats[row.status] += 1;
  }
  return stats;
}

function statusOf(value: unknown): BatchRowStatus | null {
  if (
    value === "queued" ||
    value === "running" ||
    value === "succeeded" ||
    value === "failed" ||
    value === "skipped" ||
    value === "cancelled"
  ) {
    return value;
  }
  return null;
}

function numberOf(value: unknown): number {
  return typeof value === "number" ? value : Number.NaN;
}

function stringOf(value: unknown): string {
  return typeof value === "string" ? value : "";
}

export function batchIsLive(rows: BatchRowRecord[]): boolean {
  return rows.some((row) => row.status === "queued" || row.status === "running");
}
