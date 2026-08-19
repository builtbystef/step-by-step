import { describe, expect, it } from "vitest";

import { restoreConsequence, versionChoices, versionPath, viewedVersion } from "./versions";

/**
 * The version surface, read back without a screen: what the header's dropdown
 * offers, which entry an address is showing, and what restoring one costs.
 */

/** Three Versions, as the backend lists them: oldest first. */
const PUBLISHED = [
  { number: 1, created_at: "2026-08-01T10:00:00Z" },
  { number: 2, created_at: "2026-08-05T10:00:00Z" },
  { number: 3, created_at: "2026-08-09T10:00:00Z" },
];

describe("what the version dropdown offers", () => {
  it("lists the Draft over every Version, newest first", () => {
    const choices = versionChoices(PUBLISHED, null);

    expect(choices.map((choice) => choice.label)).toEqual(["Draft", "v3", "v2", "v1"]);
  });

  it("offers the Draft alone before a first publish", () => {
    expect(versionChoices([], null)).toEqual([
      { label: "Draft", version: null, publishedAt: null, open: true },
    ]);
  });

  it("carries when each Version was published, and nothing for the Draft", () => {
    const choices = versionChoices(PUBLISHED, null);

    expect(choices[0]?.publishedAt).toBeNull();
    expect(choices[1]?.publishedAt).toBe("2026-08-09T10:00:00Z");
  });

  it("marks the Draft open while no Version is being shown", () => {
    const open = versionChoices(PUBLISHED, null).filter((choice) => choice.open);

    expect(open.map((choice) => choice.version)).toEqual([null]);
  });

  it("marks the Version being shown open, and the Draft not", () => {
    const open = versionChoices(PUBLISHED, 2).filter((choice) => choice.open);

    expect(open.map((choice) => choice.version)).toEqual([2]);
  });
});

describe("the address a choice opens", () => {
  it("is the editor itself for the Draft", () => {
    expect(versionPath("w1", null)).toBe("/workflows/w1/editor");
  });

  it("names the Version in the query, so a past Version is linkable", () => {
    expect(versionPath("w1", 3)).toBe("/workflows/w1/editor?version=3");
  });
});

describe("the Version an address is showing", () => {
  it("reads the number out of the query", () => {
    expect(viewedVersion("3")).toBe(3);
  });

  it("is the Draft when the address names no Version", () => {
    expect(viewedVersion(null)).toBeNull();
  });

  it("is the Draft for anything that is not a Version number", () => {
    expect(viewedVersion("")).toBeNull();
    expect(viewedVersion("draft")).toBeNull();
    expect(viewedVersion("0")).toBeNull();
    expect(viewedVersion("-2")).toBeNull();
    expect(viewedVersion("2.5")).toBeNull();
  });
});

describe("what restoring says it will do", () => {
  it("warns that unpublished work goes, when the Draft carries some", () => {
    const said = restoreConsequence(2, "unpublished-changes");

    expect(said).toContain("v2");
    expect(said).toContain("no Version carries");
  });

  it("says plainly what is replaced, when the Draft matches what is published", () => {
    const said = restoreConsequence(2, "in-sync");

    expect(said).toContain("v2");
    expect(said).not.toContain("no Version carries");
  });

  it("says restoring changes nothing that runs, either way", () => {
    expect(restoreConsequence(2, "in-sync")).toContain("until you publish");
    expect(restoreConsequence(2, "unpublished-changes")).toContain("until you publish");
  });
});
