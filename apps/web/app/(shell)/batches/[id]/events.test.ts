import type {
  AttemptRecord,
  BatchDetail,
  BatchRecord,
  BatchRowRecord,
  BatchStats,
} from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import { applyBatchEvent, snapshotFromDetail, type BatchSnapshot } from "./events";
import { liveRowIndex, rowChipState, statsView } from "./presentation";

const START = "2026-08-26T12:00:00.000Z";
const T = (seconds: number) => new Date(Date.parse(START) + seconds * 1000).toISOString();

function batch(): BatchRecord {
  return {
    id: "bat-1",
    name: "August invoices",
    workflow_id: "wf-1",
    created_at: T(0),
    cancelled_at: null,
  };
}

function stats(overrides: Partial<BatchStats> = {}): BatchStats {
  return {
    queued: 0,
    running: 0,
    succeeded: 0,
    failed: 0,
    skipped: 0,
    cancelled: 0,
    ...overrides,
  };
}

function attempt(overrides: Partial<AttemptRecord> = {}): AttemptRecord {
  return {
    id: "run-1",
    status: "running",
    failure_reason: null,
    queued_at: T(0),
    started_at: T(0),
    ended_at: null,
    ...overrides,
  };
}

function row(overrides: Partial<BatchRowRecord> = {}): BatchRowRecord {
  return {
    index: 0,
    variables: { city: "Belgrade" },
    status: "queued",
    latest_run_id: null,
    runs: [],
    ...overrides,
  };
}

function fiveQueued(): BatchRowRecord[] {
  return [0, 1, 2, 3, 4].map((index) =>
    row({
      index,
      status: index === 0 ? "running" : "queued",
      latest_run_id: index === 0 ? "run-0" : null,
      runs: index === 0 ? [attempt({ id: "run-0" })] : [],
      variables: { city: `city-${String(index)}` },
    }),
  );
}

function detail(rows: BatchRowRecord[]): BatchDetail {
  return {
    batch: batch(),
    rows,
    stats: stats({ running: 1, queued: 4 }),
    eta_seconds: null,
  };
}

describe("a five-row Batch as batch.row events arrive", () => {
  it("moves the live badge row to row without a reload", () => {
    let state: BatchSnapshot = snapshotFromDetail(detail(fiveQueued()));
    expect(liveRowIndex(state.rows)).toBe(0);

    state = applyBatchEvent(state, {
      type: "batch.row",
      data: { batch_id: "bat-1", row_index: 0, status: "succeeded", run_id: "run-0", at: T(40) },
    });
    state = applyBatchEvent(state, {
      type: "batch.row",
      data: { batch_id: "bat-1", row_index: 1, status: "running", run_id: "run-1", at: T(40) },
    });
    expect(liveRowIndex(state.rows)).toBe(1);
    expect(state.rows[0]?.status).toBe("succeeded");
    expect(state.rows[1]?.latest_run_id).toBe("run-1");
    expect(statsView(state.rows)).toMatchObject({ done: 1, succeeded: 1, queued: 3 });

    state = applyBatchEvent(state, {
      type: "batch.row",
      data: { batch_id: "bat-1", row_index: 1, status: "succeeded", run_id: "run-1", at: T(80) },
    });
    state = applyBatchEvent(state, {
      type: "batch.row",
      data: { batch_id: "bat-1", row_index: 2, status: "running", run_id: "run-2", at: T(80) },
    });
    expect(liveRowIndex(state.rows)).toBe(2);
  });
});

describe("skipping the waiting row", () => {
  it("marks that row skipped and moves the badge to the next row", () => {
    let state = snapshotFromDetail(detail(fiveQueued()));
    state = applyBatchEvent(state, {
      type: "batch.row",
      data: { batch_id: "bat-1", row_index: 0, status: "skipped", run_id: "run-0", at: T(10) },
    });
    state = applyBatchEvent(state, {
      type: "batch.row",
      data: { batch_id: "bat-1", row_index: 1, status: "running", run_id: "run-1", at: T(10) },
    });
    expect(state.rows[0]?.status).toBe("skipped");
    expect(liveRowIndex(state.rows)).toBe(1);
    expect(statsView(state.rows).skipped).toBe(1);
  });
});

describe("re-running a failed row", () => {
  it("attaches a new attempt and the row's chip follows it", () => {
    const failed = fiveQueued();
    failed[1] = row({
      index: 1,
      status: "failed",
      latest_run_id: "run-old",
      runs: [
        attempt({
          id: "run-old",
          status: "failed",
          failure_reason: "step_failed",
          ended_at: T(20),
        }),
      ],
    });
    let state = snapshotFromDetail(detail(failed));
    expect(rowChipState(state.rows[1]!)).toBe("failed");

    state = applyBatchEvent(state, {
      type: "batch.row",
      data: { batch_id: "bat-1", row_index: 1, status: "running", run_id: "run-new", at: T(90) },
    });
    const next = state.rows[1];
    expect(next?.status).toBe("running");
    expect(next?.latest_run_id).toBe("run-new");
    expect(next?.runs[next.runs.length - 1]?.id).toBe("run-new");
    expect(rowChipState(next!)).toBe("running");
    expect(next?.runs.some((item) => item.id === "run-old")).toBe(true);
  });
});
