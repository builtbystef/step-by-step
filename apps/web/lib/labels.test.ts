import { describe, expect, it } from "vitest";

import {
  CONNECTION_STATES,
  LIFECYCLE_STATES,
  connectionLabel,
  lifecycleLabel,
  lifecycleTone,
} from "./labels";

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

describe("connection labels", () => {
  it("names the extension in every state, so a lone 'not connected' is not shown", () => {
    expect(connectionLabel("connected")).toBe("extension connected");
    expect(connectionLabel("not_connected")).toBe("extension not connected");
    expect(connectionLabel("out_of_date")).toBe("extension out of date");
  });

  it("words every connection state", () => {
    for (const state of CONNECTION_STATES) {
      expect(connectionLabel(state)).not.toBe("");
    }
  });
});
