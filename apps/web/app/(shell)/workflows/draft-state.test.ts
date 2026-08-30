import { describe, expect, it } from "vitest";

import { draftStateBadge, refusalToRun } from "./draft-state";

import { COPY } from "../../../lib/copy";

describe("the draft-state badge", () => {
  it("is neutral until a first publish, and says so plainly", () => {
    const badge = draftStateBadge("never-published", null);

    expect(badge.tone).toBe("neutral");
    expect(badge.label).toBe("not published yet");
  });

  it("is amber while the Draft is ahead of what runs", () => {
    expect(draftStateBadge("unpublished-changes", 4).tone).toBe("wait");
    expect(draftStateBadge("unpublished-changes", 4).label).toBe("unpublished changes");
  });

  it("names the Version it is in sync with, so the row says which one runs", () => {
    const badge = draftStateBadge("in-sync", 4);

    expect(badge.tone).toBe("ok");
    expect(badge.label).toBe("in sync with v4");
  });
});

describe("what refuses to run", () => {
  it("refuses a Workflow that has published nothing, in the shared sentence", () => {
    expect(refusalToRun("never-published")).toBe(COPY.noPublishedVersion);
  });

  it("refuses neither of the two states that have a Version to run", () => {
    expect(refusalToRun("unpublished-changes")).toBeNull();
    expect(refusalToRun("in-sync")).toBeNull();
  });
});
