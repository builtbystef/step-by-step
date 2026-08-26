import { describe, expect, it } from "vitest";

import {
  FILTERED_EMPTY,
  GLOBAL_EMPTY,
  STATUS_FILTERS,
  TRIGGER_FILTERS,
  WORKFLOW_EMPTY,
  columnsOf,
  hasListFilter,
  listKind,
  rowAction,
  runDurationMs,
  runHref,
  startedAt,
  triggerLabel,
} from "./presentation";

/**
 * The Runs list's decisions, read back without a DOM: what a Workflow id
 * changes, what an empty list says, and what each row shows and links to.
 */

describe("what a Workflow id changes", () => {
  it("hides the Workflow column when the list is already on one Workflow", () => {
    expect(columnsOf(undefined)).toContain("workflow");
    expect(columnsOf("wf-1")).not.toContain("workflow");
  });

  it("does not otherwise change the columns", () => {
    expect(columnsOf(undefined).filter((column) => column !== "workflow")).toEqual(
      columnsOf("wf-1"),
    );
  });
});

describe("empty versus filtered-empty", () => {
  it("uses the global empty state verbatim", () => {
    expect(GLOBAL_EMPTY.absence).toBe("Nothing has run yet");
    expect(GLOBAL_EMPTY.whatFillsIt).toBe(
      "Runs appear here whether you start them by hand, on a schedule, or as a batch.",
    );
    expect(GLOBAL_EMPTY.action).toBe("Go to Workflows");
  });

  it("swaps that empty state for the Workflow's own call to action", () => {
    expect(WORKFLOW_EMPTY.absence).toBe("This Workflow has not run yet");
    expect(WORKFLOW_EMPTY.action).toBe("Run");
  });

  it("keeps a filter matching nothing inside the table, never as the empty state", () => {
    expect(listKind({ loaded: true, itemCount: 0, filters: {} })).toBe("empty");
    expect(listKind({ loaded: true, itemCount: 0, filters: { status: "failed" } })).toBe(
      "filtered",
    );
    expect(listKind({ loaded: true, itemCount: 3, filters: { status: "failed" } })).toBe("rows");
    expect(listKind({ loaded: false, itemCount: 0, filters: {} })).toBe("loading");
    expect(FILTERED_EMPTY).toBe("No Run matches these filters.");
  });

  it("does not treat a Workflow scope as a filter", () => {
    expect(hasListFilter({ workflow_id: "wf-1" })).toBe(false);
    expect(hasListFilter({ workflow_id: "wf-1", trigger: "manual" })).toBe(true);
  });
});

describe("the row", () => {
  it("navigates to the run detail rather than expanding", () => {
    expect(runHref("run-1")).toBe("/runs/run-1");
  });

  it("offers Take control only while the Run is waiting", () => {
    expect(rowAction("waiting_for_human")).toBe("take-control");
    expect(rowAction("running")).toBe("open");
    expect(rowAction("queued")).toBe("open");
    expect(rowAction("succeeded")).toBe("open");
  });

  it("starts from started_at, and from queued_at before the Worker claims it", () => {
    expect(
      startedAt({ started_at: "2026-08-26T12:00:00Z", queued_at: "2026-08-26T11:00:00Z" }),
    ).toBe("2026-08-26T12:00:00Z");
    expect(startedAt({ started_at: null, queued_at: "2026-08-26T11:00:00Z" })).toBe(
      "2026-08-26T11:00:00Z",
    );
  });

  it("measures duration from start to end, and to now while still running", () => {
    expect(
      runDurationMs(
        { started_at: "2026-08-26T12:00:00Z", ended_at: "2026-08-26T12:01:30Z" },
        new Date("2026-08-26T13:00:00Z"),
      ),
    ).toBe(90_000);
    expect(
      runDurationMs(
        { started_at: "2026-08-26T12:00:00Z", ended_at: null },
        new Date("2026-08-26T12:00:10Z"),
      ),
    ).toBe(10_000);
    expect(runDurationMs({ started_at: null, ended_at: null })).toBeNull();
  });

  it("labels a trigger as the word the filter uses", () => {
    expect(triggerLabel("manual")).toBe("manual");
    expect(triggerLabel("schedule")).toBe("schedule");
    expect(triggerLabel("batch")).toBe("batch");
    expect(triggerLabel("test")).toBe("test");
  });
});

describe("the filters", () => {
  it("offers every Run status and every trigger, including an any-value", () => {
    expect(STATUS_FILTERS.map((option) => option.value)).toEqual([
      "",
      "queued",
      "running",
      "waiting_for_human",
      "succeeded",
      "failed",
      "cancelled",
    ]);
    expect(TRIGGER_FILTERS.map((option) => option.value)).toEqual([
      "",
      "manual",
      "schedule",
      "batch",
      "test",
    ]);
  });

  it("words waiting as needs you, matching the chip", () => {
    expect(STATUS_FILTERS.find((option) => option.value === "waiting_for_human")?.label).toBe(
      "needs you",
    );
  });
});
