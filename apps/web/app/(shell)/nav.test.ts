import { describe, expect, it } from "vitest";

import { isCurrentSection, NAV_DESTINATIONS, SETTINGS_DESTINATION } from "./nav";

describe("the nav", () => {
  it("offers the three destinations, in the order the sidebar renders them", () => {
    expect(NAV_DESTINATIONS.map((item) => [item.label, item.path])).toEqual([
      ["Workflows", "/workflows"],
      ["Runs", "/runs"],
      ["Schedules", "/schedules"],
    ]);
  });

  it("keeps Settings out of the sidebar destinations", () => {
    expect(NAV_DESTINATIONS).not.toContain(SETTINGS_DESTINATION);
    expect(SETTINGS_DESTINATION.path).toBe("/settings");
  });

  it("does not offer a global Batches destination", () => {
    expect(NAV_DESTINATIONS.map((item) => item.label)).not.toContain("Batches");
    expect(NAV_DESTINATIONS.map((item) => item.path)).not.toContain("/batches");
  });
});

describe("which item the address lights up", () => {
  it("lights the destination itself", () => {
    expect(isCurrentSection("/runs", "/runs")).toBe(true);
  });

  it("lights it from anywhere beneath it, so a Run detail is still Runs", () => {
    expect(isCurrentSection("/runs/3f0d7c1e", "/runs")).toBe(true);
    expect(isCurrentSection("/settings/organization/members", "/settings")).toBe(true);
  });

  it("ignores the query, which is a filter rather than a place", () => {
    expect(isCurrentSection("/runs?status=failed", "/runs")).toBe(true);
  });

  it("does not light a destination whose name merely begins the address", () => {
    expect(isCurrentSection("/schedules-archive", "/schedules")).toBe(false);
  });

  it("lights nothing on an address of its own", () => {
    expect(isCurrentSection("/workflows", "/runs")).toBe(false);
  });
});
