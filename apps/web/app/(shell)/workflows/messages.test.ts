import { describe, expect, it } from "vitest";

import { deletionConsequence, refusalMessage, scheduleIndicator } from "./messages";

import { COPY } from "../../../lib/copy";

const REFUSALS = [
  "workflow_not_found",
  "no_published_version",
  "missing_secret",
  "bad_cursor",
  "not_a_member",
  "run_active",
];

describe("what a refusal says", () => {
  it("says something different for every refusal these routes answer with", () => {
    const said = REFUSALS.map((code) => refusalMessage({ code, message: "" }));

    expect(new Set(said).size).toBe(REFUSALS.length);
  });

  it("renders a Workflow with nothing published as the one shared sentence", () => {
    expect(refusalMessage({ code: "no_published_version", message: "" })).toBe(
      COPY.noPublishedVersion,
    );
  });

  it("surfaces a live-Run refusal in the delete dialog", () => {
    expect(refusalMessage({ code: "run_active", message: "" })).toMatch(/still going/);
  });

  it("falls back rather than showing the backend's prose", () => {
    expect(refusalMessage({ code: "teapot", message: "I am a teapot" })).not.toMatch(/teapot/);
    expect(refusalMessage(null)).toBe(refusalMessage({ code: "teapot", message: "" }));
  });
});

describe("what the delete dialog names", () => {
  it("names the Draft, because deleting a Workflow deletes what was recorded", () => {
    expect(deletionConsequence({ draft_state: "never-published" })).toMatch(/Draft/);
  });

  it("names the Versions when there are some, and counts them", () => {
    expect(deletionConsequence({ draft_state: "in-sync", published_version: 4 })).toMatch(
      /4 published Versions/,
    );
    expect(deletionConsequence({ draft_state: "in-sync", published_version: 1 })).toMatch(
      /1 published Version\b/,
    );
  });

  it("names no Version at all when nothing was ever published", () => {
    expect(deletionConsequence({ draft_state: "never-published" })).not.toMatch(/Version/);
  });

  it("says it cannot be undone, because it cannot", () => {
    expect(deletionConsequence({ draft_state: "never-published" })).toMatch(/cannot be undone/);
  });

  it("names the Schedules and Runs that go with it", () => {
    expect(
      deletionConsequence({
        draft_state: "in-sync",
        published_version: 1,
        schedule_count: 3,
        run_count: 42,
      }),
    ).toMatch(/3 Schedules and 42 Runs will be deleted/);
  });

  it("names a single Schedule or Run without a plural", () => {
    expect(
      deletionConsequence({
        draft_state: "never-published",
        schedule_count: 1,
        run_count: 1,
      }),
    ).toMatch(/1 Schedule and 1 Run will be deleted/);
  });

  it("names only the counts that are not zero", () => {
    expect(deletionConsequence({ draft_state: "never-published", run_count: 4 })).toMatch(
      /4 Runs will be deleted/,
    );
    expect(deletionConsequence({ draft_state: "never-published", run_count: 4 })).not.toMatch(
      /Schedule/,
    );
  });
});

describe("the schedule indicator on a row", () => {
  it("is the single-schedule label when there is one", () => {
    expect(scheduleIndicator({ schedule_count: 1, schedule_label: "weekdays 09:00" })).toBe(
      "weekdays 09:00",
    );
  });

  it("is a count when there are several", () => {
    expect(scheduleIndicator({ schedule_count: 3 })).toBe("3 schedules");
  });

  it("is nothing when there are none", () => {
    expect(scheduleIndicator({ schedule_count: 0 })).toBeNull();
  });
});
