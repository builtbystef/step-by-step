import { describe, expect, it } from "vitest";

import { OVERFLOW_ACTIONS, RUN, disabledReason } from "./actions";

import { COPY } from "../../../lib/copy";

/**
 * What a Workflow row and the Workflow header both offer, and which of those
 * a Workflow that has published nothing may not use.
 */

describe("the actions a Workflow offers", () => {
  it("offers the overflow the spec names, in order", () => {
    expect(OVERFLOW_ACTIONS.map((action) => action.label)).toEqual([
      "New batch",
      "New schedule",
      "Duplicate",
      "Rename",
      "Delete",
    ]);
  });
});

describe("what a Workflow with nothing published may not do", () => {
  it("refuses the three that act on a Version, in the one shared sentence", () => {
    const refused = [RUN, ...OVERFLOW_ACTIONS].filter(
      (action) => disabledReason(action, "never-published") !== null,
    );

    expect(refused.map((action) => action.label)).toEqual(["Run", "New batch", "New schedule"]);
    expect(disabledReason(RUN, "never-published")).toBe(COPY.noPublishedVersion);
  });

  it("leaves housekeeping alone: a Workflow nobody published is still deletable", () => {
    for (const action of OVERFLOW_ACTIONS.filter((offered) => !offered.needsAVersion)) {
      expect(disabledReason(action, "never-published")).toBeNull();
    }
  });

  it("refuses nothing once a Version exists", () => {
    for (const action of [RUN, ...OVERFLOW_ACTIONS]) {
      expect(disabledReason(action, "in-sync")).toBeNull();
      expect(disabledReason(action, "unpublished-changes")).toBeNull();
    }
  });
});
