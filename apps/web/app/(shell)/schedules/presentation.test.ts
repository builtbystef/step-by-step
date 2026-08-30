import type { OccurrenceHistoryEntry, RunHistoryEntry } from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import {
  FILTERED_EMPTY,
  GLOBAL_EMPTY,
  WORKFLOW_EMPTY,
  columnsOf,
  enabledPatch,
  hasListFilter,
  hatchOf,
  historyItems,
  holeStory,
  listKind,
  needsValuesBanner,
  noteOf,
  overlapBanner,
  recurrenceHeadline,
  recurrenceSubline,
  runHref,
  runNowRefusal,
  stripMarks,
} from "./presentation";

import { occurrenceLabel } from "../workflows/[id]/schedules/creation";
import { editSchedulePath } from "../workflows/[id]/tabs";
import { OVERFLOW_ACTIONS, RUN, disabledReason } from "../workflows/actions";
import { COPY } from "../../../lib/copy";

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
    expect(GLOBAL_EMPTY.absence).toBe("Nothing runs on a clock yet");
    expect(GLOBAL_EMPTY.whatFillsIt).toBe(
      "A Schedule fires a published Workflow on a recurrence you choose, with a value set it owns.",
    );
    expect(GLOBAL_EMPTY.action).toBe("Go to Workflows");
  });

  it("swaps that empty state for the Workflow's own call to action", () => {
    expect(WORKFLOW_EMPTY.absence).toBe("This Workflow has no Schedule yet");
    expect(WORKFLOW_EMPTY.action).toBe("New schedule");
  });

  it("keeps a filter matching nothing inside the table, never as the empty state", () => {
    expect(listKind({ loaded: true, itemCount: 0, filters: {} })).toBe("empty");
    expect(listKind({ loaded: true, itemCount: 0, filters: { status: "paused" } })).toBe(
      "filtered",
    );
    expect(listKind({ loaded: true, itemCount: 3, filters: { status: "paused" } })).toBe("rows");
    expect(listKind({ loaded: false, itemCount: 0, filters: {} })).toBe("loading");
    expect(FILTERED_EMPTY).toBe("No Schedule matches these filters.");
  });

  it("does not treat a Workflow scope as a filter", () => {
    expect(hasListFilter({ workflow_id: "wf-1" })).toBe(false);
    expect(hasListFilter({ workflow_id: "wf-1", status: "paused" })).toBe(true);
  });

  it("disables New schedule behind the shared sentence while never-published", () => {
    const action = OVERFLOW_ACTIONS.find((item) => item.label === WORKFLOW_EMPTY.action);
    expect(action?.key).toBe("new-schedule");
    expect(disabledReason(action!, "never-published")).toBe(COPY.noPublishedVersion);
    expect(disabledReason(RUN, "never-published")).toBe(COPY.noPublishedVersion);
    expect(disabledReason(action!, "in-sync")).toBeNull();
  });
});

describe("the Schedule row", () => {
  it("shows the recurrence in words with cron and timezone beneath", () => {
    expect(recurrenceHeadline("0 9 * * 1-5")).toBe("every weekday at 09:00");
    expect(recurrenceSubline("0 9 * * 1-5", "Europe/Belgrade")).toEqual({
      cron: "0 9 * * 1-5",
      timezone: "Europe/Belgrade",
    });
  });

  it("shows the raw expression when the grammar cannot phrase it", () => {
    expect(recurrenceHeadline("*/7 3-5 * * *")).toBe("*/7 3-5 * * *");
  });

  it("carries the latest non-firing Occurrence in the note, and is empty when healthy", () => {
    expect(noteOf(null)).toBe("");
    expect(noteOf({ occurrence_at: "2026-08-26T07:00:00.000Z", reason: "overlap" })).toContain(
      "still running",
    );
    expect(noteOf({ occurrence_at: "2026-08-26T07:00:00.000Z", reason: "missed" })).toContain(
      "not running",
    );
    expect(
      noteOf({ occurrence_at: "2026-08-26T07:00:00.000Z", reason: "missing_values" }, ["region"]),
    ).toContain("region");
  });
});

const RUN_A: RunHistoryEntry = {
  kind: "run",
  at: "2026-08-24T07:00:00.000Z",
  run_id: "run-a",
  status: "succeeded",
};
const OVERLAP: OccurrenceHistoryEntry = {
  kind: "occurrence",
  at: "2026-08-25T07:00:00.000Z",
  reason: "overlap",
  blocking_run_id: "run-a",
};
const RUN_B: RunHistoryEntry = {
  kind: "run",
  at: "2026-08-26T07:00:00.000Z",
  run_id: "run-b",
  status: "failed",
};
const MISSED: OccurrenceHistoryEntry = {
  kind: "occurrence",
  at: "2026-08-23T07:00:00.000Z",
  reason: "missed",
};
const MISSING: OccurrenceHistoryEntry = {
  kind: "occurrence",
  at: "2026-08-22T07:00:00.000Z",
  reason: "missing_values",
};

describe("the Occurrence strip and history", () => {
  it("renders Runs and the three hole kinds as four distinct marks, past and future on one line", () => {
    const marks = stripMarks({
      history: [MISSING, MISSED, RUN_A, OVERLAP],
      nextOccurrences: ["2026-08-27T07:00:00.000Z", "2026-08-28T07:00:00.000Z"],
      paused: false,
    });
    expect(marks.map((mark) => mark.kind)).toEqual([
      "missing_values",
      "missed",
      "run",
      "overlap",
      "due",
      "due",
    ]);
    expect(new Set([hatchOf("overlap"), hatchOf("missed"), hatchOf("missing_values")]).size).toBe(
      3,
    );
  });

  it("reads two Runs and one overlap as three history entries in time order, of both kinds", () => {
    const items = historyItems([RUN_A, OVERLAP, RUN_B]);
    expect(items).toEqual([
      { kind: "run", at: RUN_A.at, runId: "run-a", status: "succeeded" },
      {
        kind: "occurrence",
        at: OVERLAP.at,
        reason: "overlap",
        blockingRunId: "run-a",
      },
      { kind: "run", at: RUN_B.at, runId: "run-b", status: "failed" },
    ]);
    expect(items.map((item) => item.kind)).toEqual(["run", "occurrence", "run"]);
  });
});

describe("the overlap banner and the three stories", () => {
  it("names the blocking Run and its reason, and points at that Run", () => {
    const banner = overlapBanner({
      occurrence_at: "2026-08-25T07:00:00.000Z",
      reason: "overlap",
      blocking_run_id: "run-a",
    });
    expect(banner).not.toBeNull();
    expect(banner?.story).toMatch(/still running/);
    expect(banner?.blockingRunId).toBe("run-a");
    expect(banner?.openHref).toBe(runHref("run-a"));
    expect(banner?.openLabel).toBe("Open the Run that blocked it");
    expect(banner?.runNowLabel).toBe("Run it now instead");
  });

  it("surfaces a schedule_run_active refusal in place, not swallowed", () => {
    expect(runNowRefusal({ code: "schedule_run_active" })).toMatch(/still/);
    expect(runNowRefusal({ code: "schedule_run_active" })).not.toBe("");
    expect(runNowRefusal(null)).toBeNull();
  });

  it("tells overlap, missed, and missing_values as three distinct stories", () => {
    expect(holeStory("overlap")).toMatch(/previous Run was still running/);
    expect(holeStory("missed")).toMatch(/instance was not running/);
    expect(holeStory("missed")).toMatch(/never run late/);
    expect(holeStory("missing_values", ["region"])).toMatch(/needs region/);
    expect(holeStory("overlap")).not.toBe(holeStory("missed"));
    expect(holeStory("missed")).not.toBe(holeStory("missing_values", ["region"]));
  });
});

describe("needs_values versus paused", () => {
  it("names the missing Variables on a red banner whose control opens the value set", () => {
    const banner = needsValuesBanner({
      state: "needs_values",
      missingVariableNames: ["region"],
      workflowId: "wf-1",
      scheduleId: "sch-1",
    });
    expect(banner).not.toBeNull();
    expect(banner?.tone).toBe("bad");
    expect(banner?.names).toEqual(["region"]);
    expect(banner?.setValuesHref).toBe(editSchedulePath("wf-1", "sch-1"));
    expect(banner?.setValuesLabel).toMatch(/set/i);
  });

  it("does not look like paused: paused has a band and no red banner, and accrues no holes", () => {
    expect(
      needsValuesBanner({
        state: "paused",
        missingVariableNames: [],
        workflowId: "wf-1",
        scheduleId: "sch-1",
      }),
    ).toBeNull();
    expect(
      stripMarks({
        history: [RUN_A],
        nextOccurrences: ["2026-08-27T07:00:00.000Z"],
        paused: true,
      }).map((mark) => mark.kind),
    ).toEqual(["run", "paused"]);
  });
});

describe("the enabled toggle", () => {
  it("patches enabled", () => {
    expect(enabledPatch(false)).toEqual({ enabled: false });
    expect(enabledPatch(true)).toEqual({ enabled: true });
  });
});

describe("next Occurrences", () => {
  it("appear in the Schedule's timezone with the viewer's differing local time in grey", () => {
    const same = occurrenceLabel("2026-08-26T07:00:00.000Z", "Europe/Belgrade", "Europe/Belgrade");
    expect(same.at).toContain("09:00");
    expect(same.local).toBeNull();

    const differs = occurrenceLabel(
      "2026-08-26T07:00:00.000Z",
      "Europe/Belgrade",
      "America/New_York",
    );
    expect(differs.at).toContain("09:00");
    expect(differs.local).toContain("03:00");
  });
});
