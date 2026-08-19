import { describe, expect, it } from "vitest";

import { deletionConsequence, refusalMessage } from "./messages";

import { COPY } from "../../../lib/copy";

/**
 * What the Workflows screens say when a route refuses them, and what the
 * delete dialog names before it is agreed to.
 */

const REFUSALS = ["workflow_not_found", "no_published_version", "bad_cursor", "not_a_member"];

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
});
