import { describe, expect, it } from "vitest";

import { EDITOR, WORKFLOW_TABS, tabAt, tabPath } from "./tabs";

/**
 * The Workflow page's four tabs, read back as the addresses they are: each is
 * its own URL, which is what makes a tab linkable and the back button walk
 * them rather than leave the page.
 */

const WORKFLOW = "3f1a";

describe("the Workflow page's tabs", () => {
  it("offers the four the spec names, in order, Editor first", () => {
    expect(WORKFLOW_TABS.map((tab) => tab.segment)).toEqual([
      "editor",
      "runs",
      "schedules",
      "batches",
    ]);
    expect(EDITOR.segment).toBe("editor");
  });

  it("gives each tab a URL of its own beneath the Workflow", () => {
    const paths = WORKFLOW_TABS.map((tab) => tabPath(WORKFLOW, tab));

    expect(paths).toEqual([
      "/workflows/3f1a/editor",
      "/workflows/3f1a/runs",
      "/workflows/3f1a/schedules",
      "/workflows/3f1a/batches",
    ]);
    expect(new Set(paths).size).toBe(WORKFLOW_TABS.length);
  });

  it("reads back which tab an address is on", () => {
    expect(tabAt("/workflows/3f1a/runs")?.label).toBe("Runs");
    expect(tabAt("/workflows/3f1a/editor")).toBe(EDITOR);
  });

  it("reads the bare Workflow address as the tab it redirects to", () => {
    expect(tabAt("/workflows/3f1a")).toBe(EDITOR);
  });

  it("knows no tab outside a Workflow, whatever the address looks like", () => {
    expect(tabAt("/workflows")).toBeNull();
    expect(tabAt("/runs")).toBeNull();
    expect(tabAt("/workflows/3f1a/settings")).toBeNull();
  });
});
