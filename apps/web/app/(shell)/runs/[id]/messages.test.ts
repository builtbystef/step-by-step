import { describe, expect, it } from "vitest";

import { COPY } from "../../../../lib/copy";

import { refusalMessage } from "./messages";

describe("cockpit refusals", () => {
  it("names a missing Run rather than leaking that it exists elsewhere", () => {
    expect(refusalMessage({ code: "run_not_found" })).toBe(
      "That Run is gone. Somebody deleted it, or it was never here.",
    );
  });

  it("reuses the shared unpublished-Version sentence", () => {
    expect(refusalMessage({ code: "no_published_version" })).toBe(COPY.noPublishedVersion);
  });

  it("names a takeover that another session already holds", () => {
    expect(refusalMessage({ code: "already_held" })).toBe("Control is held in another tab.");
  });
});
