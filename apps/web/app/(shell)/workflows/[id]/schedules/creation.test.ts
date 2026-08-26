import type { Variable } from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import { columnsOf, emptyRow } from "../../../../../components/value-grid/grid";
import { fromCron, humanize, toCron } from "../../../../../lib/recurrence";

import {
  applyPreset,
  cronOf,
  defaultTimezone,
  emptyVariableNames,
  lastNonTestVariables,
  occurrenceLabel,
  openExisting,
  previewBody,
  scheduleBody,
  schedulesHref,
  writeCronInstead,
} from "./creation";

/**
 * The Schedule creation page's decisions, read back without a DOM: the
 * preset chips, the sentence ↔ cron bridge, the preview request, the
 * timezone default, fill-from-last-Run, the empty-value refusal, and the
 * save payload.
 */

const CITY: Variable = { name: "city" };
const PASSWORD: Variable = {
  name: "password",
  secret: true,
  secretId: "sec-1",
  secretName: "acme-portal-password",
};

describe("the weekdays 09:00 chip", () => {
  it("fills the sentence, shows the cron, reads it back, and asks the preview for times", () => {
    const recurrence = applyPreset("weekdays09");
    expect(recurrence).toEqual({ kind: "weekdays", hour: 9, minute: 0 });

    const cron = toCron(recurrence!);
    expect(cron).toBe("0 9 * * 1-5");
    expect(fromCron(cron)).toEqual(recurrence);
    expect(humanize(cron)).toBe("every weekday at 09:00");
    expect(previewBody(cron, "Europe/Belgrade")).toEqual({
      cron: "0 9 * * 1-5",
      timezone: "Europe/Belgrade",
    });
  });
});

describe("editing the sentence and writing cron instead", () => {
  it("regenerates the cron when the sentence changes", () => {
    expect(cronOf({ raw: false, recurrence: { kind: "daily", hour: 10, minute: 30 } })).toBe(
      "30 10 * * *",
    );
  });

  it("accepts a raw expression the grammar declines, and still asks the preview", () => {
    const mode = writeCronInstead("*/7 3-5 * * *");
    expect(mode).toEqual({ raw: true, cron: "*/7 3-5 * * *" });
    expect(cronOf(mode)).toBe("*/7 3-5 * * *");
    expect(humanize(cronOf(mode))).toBeNull();
    expect(previewBody(cronOf(mode), "UTC")).toEqual({
      cron: "*/7 3-5 * * *",
      timezone: "UTC",
    });
  });
});

describe("opening an existing Schedule", () => {
  it("lands in raw-cron mode when the grammar cannot hold the expression", () => {
    expect(openExisting("*/7 3-5 * * *")).toEqual({ raw: true, cron: "*/7 3-5 * * *" });
  });

  it("fills the sentence when the expression is in the grammar", () => {
    expect(openExisting("0 9 * * 1-5")).toEqual({
      raw: false,
      recurrence: { kind: "weekdays", hour: 9, minute: 0 },
    });
  });
});

describe("the timezone default and the save", () => {
  it("defaults to the browser zone when the instance knows it, else the instance default", () => {
    const known = ["Europe/Belgrade", "UTC", "America/New_York"];
    expect(defaultTimezone("Europe/Belgrade", known, "UTC")).toBe("Europe/Belgrade");
    expect(defaultTimezone("Mars/Olympus", known, "UTC")).toBe("UTC");
    expect(defaultTimezone(undefined, known, "Europe/Belgrade")).toBe("Europe/Belgrade");
  });

  it("stores the chosen timezone explicitly on save", () => {
    expect(
      scheduleBody({
        cron: "0 9 * * 1-5",
        timezone: "Europe/Belgrade",
        enabled: true,
        variables: { city: "Belgrade" },
        name: "Morning sweep",
      }),
    ).toEqual({
      cron: "0 9 * * 1-5",
      timezone: "Europe/Belgrade",
      enabled: true,
      variables: { city: "Belgrade" },
      name: "Morning sweep",
    });
  });

  it("trails the viewer's local time when it differs from the Schedule's", () => {
    // 07:00Z is 09:00 in Belgrade (CEST) and 03:00 in New York (EDT).
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

describe("the one-row value set", () => {
  it("copies the most recent non-test Run only when asked, and never a test Run", () => {
    const columns = columnsOf([CITY, PASSWORD]);
    const empty = emptyRow(columns);
    expect(empty).toEqual({ city: "" });

    const runs = [
      { trigger: "test" as const, variables: { city: "from-test" } },
      { trigger: "manual" as const, variables: { city: "Belgrade", password: "stolen" } },
    ];
    expect(lastNonTestVariables(runs)).toEqual({ city: "Belgrade", password: "stolen" });
    expect(
      lastNonTestVariables([{ trigger: "test", variables: { city: "from-test" } }]),
    ).toBeNull();
  });

  it("refuses a save that leaves a non-secret Variable empty, naming it", () => {
    const columns = columnsOf([CITY, PASSWORD]);
    expect(emptyVariableNames({ city: "" }, columns)).toEqual(["city"]);
    expect(emptyVariableNames({ city: "   " }, columns)).toEqual(["city"]);
    expect(emptyVariableNames({ city: "Belgrade" }, columns)).toEqual([]);
  });
});

describe("the save payload", () => {
  it("sends cron, timezone, enabled, variables, and the optional name", () => {
    expect(
      scheduleBody({
        cron: "0 9 * * 1-5",
        timezone: "UTC",
        enabled: false,
        variables: { city: "Belgrade" },
        name: "",
      }),
    ).toEqual({
      cron: "0 9 * * 1-5",
      timezone: "UTC",
      enabled: false,
      variables: { city: "Belgrade" },
      name: null,
    });
  });

  it("navigates back to the Workflow's Schedules tab", () => {
    expect(schedulesHref("wf-1")).toBe("/workflows/wf-1/schedules");
  });
});
