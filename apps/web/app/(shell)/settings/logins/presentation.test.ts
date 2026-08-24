import { describe, expect, it } from "vitest";

import { savedLoginScope } from "./presentation";

describe("Saved login scope", () => {
  it("names the shared and caller-only layers in user-facing words", () => {
    expect(savedLoginScope("organization")).toBe("Organization login");
    expect(savedLoginScope("personal")).toBe("Your login");
  });
});
