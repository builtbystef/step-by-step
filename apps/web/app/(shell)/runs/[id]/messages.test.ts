import { describe, expect, it } from "vitest";

import { COPY } from "../../../../lib/copy";

import { refusalMessage } from "./messages";

describe("cockpit refusals", () => {
  it("names a missing Run rather than leaking that it exists elsewhere", () => {
    expect(refusalMessage({ code: "run_not_found" })).toBe(
      "That Run is gone — somebody deleted it, or it was never here.",
    );
  });

  it("reuses the shared unpublished-Version sentence", () => {
    expect(refusalMessage({ code: "no_published_version" })).toBe(COPY.noPublishedVersion);
  });
});
