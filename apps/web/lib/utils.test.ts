import { describe, expect, it } from "vitest";

import { cn } from "./utils";

/*
 * The generated components in `components/ui/` carry Tailwind's own font
 * sizes. Where a primitive sets one of the six, the six must win — which only
 * happens if tailwind-merge has been taught they are font sizes.
 */
describe("cn", () => {
  it("lets one of the six sizes replace a generated Tailwind size", () => {
    expect(cn("text-sm", "text-half")).toBe("text-half");
  });

  it("lets one of the six sizes replace an arbitrary size", () => {
    expect(cn("text-[0.8rem]", "text-small")).toBe("text-small");
  });

  it("keeps the last of two sizes from the scale", () => {
    expect(cn("text-micro", "text-body")).toBe("text-body");
  });

  it("does not treat a size as a colour", () => {
    expect(cn("text-mut", "text-body")).toBe("text-mut text-body");
  });
});
