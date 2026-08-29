import type { Target } from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import { stepBadges } from "./badges";
import { driftedStepIds, repairFromDrift } from "./drift";
import type { Step } from "./steps";

/**
 * Selector Drift on a card: an aggregate warning from recent Step Results,
 * and the one move that takes the person to the selector panel that repairs
 * it. Rank 0 is the recorded best; anything above it is drift.
 */

const FOUND_BY_NAME: Target = { candidates: [{ kind: "role", value: "Save" }] };

function clicking(id: string): Step {
  return { id, label: "Click Save", type: "click", payload: { target: FOUND_BY_NAME } };
}

describe("which Steps have drifted", () => {
  it("flags a Step whose recent Results matched above rank 0, and not one at rank 0", () => {
    const drifted = driftedStepIds([
      { step_id: "stable", matched_candidate_rank: 0 },
      { step_id: "moved", matched_candidate_rank: 2 },
      { step_id: "skipped", matched_candidate_rank: null },
    ]);

    expect(drifted.has("moved")).toBe(true);
    expect(drifted.has("stable")).toBe(false);
    expect(drifted.has("skipped")).toBe(false);
  });
});

describe("the drift badge on a card", () => {
  it("appears on a drifted Step and not on one that still matches at rank 0", () => {
    const drifted = stepBadges(clicking("moved"), 30_000, true);
    const stable = stepBadges(clicking("stable"), 30_000, false);

    expect(drifted.map((badge) => badge.key)).toContain("drift");
    expect(drifted.find((badge) => badge.key === "drift")).toMatchObject({
      label: "drifting",
      tone: "wait",
    });
    expect(stable.map((badge) => badge.key)).not.toContain("drift");
  });
});

describe("repairing from the badge", () => {
  it("leads into the selector panel of that Step", () => {
    expect(repairFromDrift("moved")).toEqual({ expand: "moved", openSelector: true });
  });
});
