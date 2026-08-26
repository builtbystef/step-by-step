import type { DraftComparison } from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import { publishPlan } from "./publish";

/**
 * What the publish modal states, read back without a screen.
 *
 * The comparisons here are the ones the backend's own worked example mints:
 * with v1 published, editing Step A, adding D, and removing C is exactly
 * changed [A], added [D], removed [C].
 */

function comparison(over: Partial<DraftComparison> = {}): DraftComparison {
  return {
    added: [],
    changed: [],
    removed: [],
    state: "unpublished-changes",
    latest_version: 1,
    stranded_schedules: [],
    ...over,
  };
}

function stranded(
  over: Partial<DraftComparison["stranded_schedules"][number]> = {},
): DraftComparison["stranded_schedules"][number] {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    name: "Morning invoices",
    cron: "0 9 * * *",
    ...over,
  };
}

describe("what publishing would mint", () => {
  it("is the number after the latest Version", () => {
    expect(publishPlan(comparison({ latest_version: 3 })).number).toBe(4);
  });

  it("is v1 when nothing has ever been published", () => {
    const plan = publishPlan(
      comparison({
        state: "never-published",
        latest_version: null,
        added: [{ id: "a", label: "Go to the invoices page" }],
      }),
    );

    expect(plan.number).toBe(1);
  });
});

describe("the step-level diff a person confirms against", () => {
  it("lists what was added, changed, and removed, by the Steps' labels", () => {
    const plan = publishPlan(
      comparison({
        added: [{ id: "d", label: "Download the report" }],
        changed: [{ id: "a", label: "Type {{tenant}} into Account" }],
        removed: [{ id: "c", label: "Click Cancel" }],
      }),
    );

    expect(plan.sections.map((section) => section.key)).toEqual(["added", "changed", "removed"]);
    expect(plan.sections.map((section) => section.steps.map((step) => step.label))).toEqual([
      ["Download the report"],
      ["Type {{tenant}} into Account"],
      ["Click Cancel"],
    ]);
  });

  it("leaves out a list nothing is in", () => {
    const plan = publishPlan(comparison({ changed: [{ id: "a", label: "Click Save" }] }));

    expect(plan.sections.map((section) => section.key)).toEqual(["changed"]);
  });

  it("shows every Step as added on a first publish, under no other heading", () => {
    const plan = publishPlan(
      comparison({
        state: "never-published",
        latest_version: null,
        added: [
          { id: "a", label: "Go to the invoices page" },
          { id: "b", label: "Click Save" },
        ],
      }),
    );

    expect(plan.sections.map((section) => section.key)).toEqual(["added"]);
    expect(plan.sections[0]?.steps).toHaveLength(2);
    expect(plan.note).toBeNull();
  });
});

describe("what the modal says when no section says it", () => {
  it("refuses a publish that would mint an identical Version", () => {
    const plan = publishPlan(comparison({ state: "in-sync", latest_version: 2 }));

    expect(plan.worthPublishing).toBe(false);
    expect(plan.note).toContain("v2");
  });

  it("says what moved when the Draft differs and no Step does", () => {
    const plan = publishPlan(comparison({ state: "unpublished-changes" }));

    expect(plan.worthPublishing).toBe(true);
    expect(plan.note).toContain("order");
    expect(plan.note).toContain("Variables");
  });

  it("says the Draft holds no Steps when a first publish has nothing to list", () => {
    const plan = publishPlan(comparison({ state: "never-published", latest_version: null }));

    expect(plan.worthPublishing).toBe(true);
    expect(plan.note).toContain("no Steps");
  });
});

describe("the warning for Schedules publishing would strand", () => {
  it("names both Schedules and states they will stop firing until their values are set", () => {
    const plan = publishPlan(
      comparison({
        stranded_schedules: [
          stranded({ name: "Morning invoices" }),
          stranded({
            id: "22222222-2222-2222-2222-222222222222",
            name: "Evening invoices",
            cron: "0 18 * * *",
          }),
        ],
      }),
    );

    expect(plan.warning).toContain("Morning invoices");
    expect(plan.warning).toContain("Evening invoices");
    expect(plan.warning).toContain("will stop firing until their values are set");
  });

  it("is absent when no Schedule would be stranded", () => {
    expect(publishPlan(comparison()).warning).toBeNull();
  });

  it("uses the recurrence sentence when a Schedule has no name", () => {
    const plan = publishPlan(
      comparison({
        stranded_schedules: [stranded({ name: null, cron: "0 9 * * 1-5" })],
      }),
    );

    expect(plan.warning).toContain("every weekday at 09:00");
    expect(plan.warning).toContain("will stop firing until its values are set");
  });
});
