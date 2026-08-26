import type { AttemptRecord, BatchRowRecord, BatchStats } from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import {
  etaLabel,
  failureReasonWords,
  liveRowIndex,
  outputDownloadHref,
  progressSegments,
  rowChipState,
  rowDurationMs,
  runHref,
  stalledCallout,
  statsView,
  takeOverLabel,
  variableColumns,
  type StalledInput,
} from "./presentation";

/**
 * The batch view's decisions, read back without a DOM: the stats header,
 * the segmented bar, the live badge, the ETA, row expansion copy, and the
 * stalled callout. The page draws these; it does not re-decide them.
 */

const START = "2026-08-26T12:00:00.000Z";
const T = (seconds: number) => new Date(Date.parse(START) + seconds * 1000).toISOString();

function attempt(overrides: Partial<AttemptRecord> = {}): AttemptRecord {
  return {
    id: "run-1",
    status: "succeeded",
    failure_reason: null,
    queued_at: T(0),
    started_at: T(0),
    ended_at: T(40),
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

function fiveRows(live: number): BatchRowRecord[] {
  return [0, 1, 2, 3, 4].map((index) => {
    if (index < live) {
      return row({
        index,
        status: "succeeded",
        latest_run_id: `run-${String(index)}`,
        runs: [attempt({ id: `run-${String(index)}` })],
        variables: { city: `city-${String(index)}` },
      });
    }
    if (index === live) {
      return row({
        index,
        status: "running",
        latest_run_id: `run-${String(index)}`,
        runs: [
          attempt({
            id: `run-${String(index)}`,
            status: "running",
            ended_at: null,
          }),
        ],
        variables: { city: `city-${String(index)}` },
      });
    }
    return row({ index, status: "queued", variables: { city: `city-${String(index)}` } });
  });
}

describe("the stats header of a five-row Batch", () => {
  it("counts done / succeeded / failed / queued / skipped from the rows", () => {
    const rows = [
      row({ index: 0, status: "succeeded" }),
      row({ index: 1, status: "failed" }),
      row({ index: 2, status: "running" }),
      row({ index: 3, status: "queued" }),
      row({ index: 4, status: "skipped" }),
    ];
    expect(statsView(rows)).toEqual({
      done: 2,
      total: 5,
      succeeded: 1,
      failed: 1,
      queued: 1,
      skipped: 1,
    });
  });

  it("folds a cancelled row into skipped, and never invents a second total", () => {
    const rows = [
      row({ index: 0, status: "succeeded" }),
      row({ index: 1, status: "cancelled" }),
      row({ index: 2, status: "queued" }),
    ];
    expect(statsView(rows)).toEqual({
      done: 1,
      total: 3,
      succeeded: 1,
      failed: 0,
      queued: 1,
      skipped: 1,
    });
  });
});

describe("the segmented progress bar", () => {
  it("lays segments in succeeded / failed / running / skipped / queued order", () => {
    const stats: BatchStats = {
      succeeded: 2,
      failed: 1,
      running: 1,
      queued: 3,
      skipped: 1,
      cancelled: 2,
    };
    expect(progressSegments(stats)).toEqual([
      { key: "succeeded", count: 2, tone: "ok" },
      { key: "failed", count: 1, tone: "bad" },
      { key: "running", count: 1, tone: "accent" },
      { key: "skipped", count: 3, tone: "neutral" },
      { key: "queued", count: 3, tone: "muted" },
    ]);
  });
});

describe("the live badge", () => {
  it("sits on the running row and nowhere else", () => {
    const rows = fiveRows(2);
    expect(liveRowIndex(rows)).toBe(2);
    expect(rows.map((_, index) => liveRowIndex(rows) === index)).toEqual([
      false,
      false,
      true,
      false,
      false,
    ]);
  });

  it("is absent when every row is finished", () => {
    expect(
      liveRowIndex([row({ index: 0, status: "succeeded" }), row({ index: 1, status: "failed" })]),
    ).toBeNull();
  });
});

describe("the ETA area", () => {
  it("is blank until the endpoint has an estimate, then shows that estimate", () => {
    expect(etaLabel(null)).toBeNull();
    expect(etaLabel(undefined)).toBeNull();
    expect(etaLabel(40)).toBe("40 s left");
    expect(etaLabel(660)).toBe("11 min left");
  });
});

describe("a row's chip and duration", () => {
  it("hands StatusChip the row status, or waiting_for_human when the live Run is", () => {
    expect(rowChipState(row({ status: "failed" }))).toBe("failed");
    expect(rowChipState(row({ status: "running" }))).toBe("running");
    expect(rowChipState(row({ status: "running" }), "waiting_for_human")).toBe("waiting_for_human");
  });

  it("measures duration from the latest attempt", () => {
    const finished = row({
      status: "succeeded",
      runs: [attempt({ started_at: T(0), ended_at: T(41) })],
    });
    expect(rowDurationMs(finished, new Date(T(100)))).toBe(41_000);

    const live = row({
      status: "running",
      runs: [attempt({ status: "running", started_at: T(0), ended_at: null })],
    });
    expect(rowDurationMs(live, new Date(T(12)))).toBe(12_000);

    expect(rowDurationMs(row({ status: "queued" }), new Date(T(12)))).toBeNull();
  });
});

describe("Variable columns", () => {
  it("are the union of the rows' keys, in first-seen order", () => {
    expect(
      variableColumns([
        row({ variables: { city: "A", region: "EU" } }),
        row({ variables: { city: "B", extra: 1 } }),
      ]),
    ).toEqual(["city", "region", "extra"]);
  });
});

describe("opening a Run from a row", () => {
  it("lands on that Run's cockpit", () => {
    expect(runHref("run-9")).toBe("/runs/run-9");
  });
});

describe("a failed row's expansion", () => {
  it("words the failure_reason and offers open-the-run and re-run", () => {
    expect(failureReasonWords("step_failed")).toBe(
      "A Step failed — a selector missed, an action errored, or the Step timed out.",
    );
    expect(failureReasonWords("takeover_timeout")).toBe("The waiting-for-you deadline passed.");
    expect(failureReasonWords("auth_challenge")).toBe(
      "A Step failed while an authentication challenge was on the page.",
    );
    expect(failureReasonWords(null)).toBe("This row failed.");
  });
});

describe("the stalled callout", () => {
  it("names the row, states the sequential rule, the timeout consequence, and the actions", () => {
    const input: StalledInput = {
      rowIndex: 1,
      queuedCount: 3,
      deadlineAt: T(1800),
      now: new Date(T(60)),
    };
    const callout = stalledCallout(input);
    expect(callout).not.toBeNull();
    expect(callout?.title).toBe("Row 2 is waiting for you");
    expect(callout?.sequential).toBe(
      "Rows run one at a time — the other 3 rows stay queued until this one is dealt with.",
    );
    expect(callout?.timeout).toBe("If the deadline passes, this row fails and the Batch moves on.");
    expect(callout?.countdown).toBe("29:00 left");
    expect(callout?.takeOver).toBe("Take over row 2");
    expect(callout?.skip).toBe("Skip this row");
    expect(takeOverLabel(2)).toBe("Take over row 2");
  });

  it("is absent when no row is waiting", () => {
    expect(stalledCallout(null)).toBeNull();
  });
});

describe("the Output tab", () => {
  it("downloads both formats from the endpoint", () => {
    expect(outputDownloadHref("bat-1", "json")).toBe("/api/batches/bat-1/output?format=json");
    expect(outputDownloadHref("bat-1", "csv")).toBe("/api/batches/bat-1/output?format=csv");
  });
});
