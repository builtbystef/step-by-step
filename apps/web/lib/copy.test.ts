import { describe, expect, it } from "vitest";

import { COPY } from "./copy";

describe("shared copy", () => {
  it("has one wording for an unpublished Version, verbatim", () => {
    expect(COPY.noPublishedVersion).toBe("Publish a Version before this Workflow can run.");
  });
});
