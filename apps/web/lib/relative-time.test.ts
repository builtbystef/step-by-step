import { describe, expect, it } from "vitest";

import { relativeTime } from "./relative-time";

/**
 * Times as a list renders them: how long ago, in the coarsest unit that still
 * says something. `Intl` does the wording; what is decided here is the unit.
 */

const NOW = new Date("2026-08-19T12:00:00Z");

describe("how long ago", () => {
  it("counts in the coarsest unit that still fits", () => {
    expect(relativeTime("2026-08-19T11:59:30Z", NOW)).toBe("30 seconds ago");
    expect(relativeTime("2026-08-19T11:40:00Z", NOW)).toBe("20 minutes ago");
    expect(relativeTime("2026-08-19T10:00:00Z", NOW)).toBe("2 hours ago");
    expect(relativeTime("2026-08-17T12:00:00Z", NOW)).toBe("2 days ago");
    expect(relativeTime("2026-07-20T12:00:00Z", NOW)).toBe("last month");
    expect(relativeTime("2024-08-19T12:00:00Z", NOW)).toBe("2 years ago");
  });

  it("says now rather than counting a second nobody noticed", () => {
    expect(relativeTime("2026-08-19T12:00:00Z", NOW)).toBe("just now");
  });

  it("reads a clock that is a moment ahead as now rather than as the future", () => {
    expect(relativeTime("2026-08-19T12:00:02Z", NOW)).toBe("just now");
  });
});
