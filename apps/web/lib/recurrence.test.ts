import { describe, expect, it } from "vitest";

import { fromCron, humanize, toCron, type Recurrence } from "./recurrence";

describe("recurrence cron grammar", () => {
  it("writes the sentence builder's canonical cron expressions", () => {
    expect(toCron({ kind: "weekdays", hour: 9, minute: 0 })).toBe("0 9 * * 1-5");
    expect(toCron({ kind: "everyNMinutes", n: 15 })).toBe("*/15 * * * *");
    expect(toCron({ kind: "monthly", day: 1, hour: 7, minute: 30 })).toBe("30 7 1 * *");
  });

  it.each<Recurrence>([
    { kind: "everyNMinutes", n: 15 },
    { kind: "hourly", minute: 20 },
    { kind: "daily", hour: 9, minute: 5 },
    { kind: "weekdays", hour: 8, minute: 45 },
    { kind: "weekly", weekdays: [1, 3, 5], hour: 12, minute: 30 },
    { kind: "monthly", day: 18, hour: 7, minute: 10 },
  ])("round-trips $kind recurrences", (recurrence) => {
    expect(fromCron(toCron(recurrence))).toEqual(recurrence);
  });

  it("declines cron expressions outside the sentence grammar", () => {
    expect(fromCron("*/7 3-5 * * *")).toBeNull();
  });

  it("reads back only cron expressions in the sentence grammar", () => {
    expect(humanize("0 9 * * 1-5")).toBe("every weekday at 09:00");
    expect(humanize("*/7 3-5 * * *")).toBeNull();
  });
});
