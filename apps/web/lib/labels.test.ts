import { describe, expect, it } from "vitest";

import { LIFECYCLE_STATES, lifecycleLabel, lifecycleTone } from "./labels";

describe("lifecycle labels", () => {
  it("words waiting_for_human as 'needs you'", () => {
    expect(lifecycleLabel("waiting_for_human")).toBe("needs you");
  });

  it("words every lifecycle state", () => {
    for (const state of LIFECYCLE_STATES) {
      expect(lifecycleLabel(state)).not.toBe("");
    }
  });

  it("tones the ramp as the visual language defines it", () => {
    expect(lifecycleTone("running")).toBe("accent");
    expect(lifecycleTone("waiting_for_human")).toBe("wait");
    expect(lifecycleTone("succeeded")).toBe("ok");
    expect(lifecycleTone("failed")).toBe("bad");
  });

  it("keeps skipped grey, beside the other resting states", () => {
    const grey = ["queued", "cancelled", "cancelling", "skipped", "missed", "paused"] as const;
    for (const state of grey) {
      expect(lifecycleTone(state)).toBe("neutral");
    }
  });
});
