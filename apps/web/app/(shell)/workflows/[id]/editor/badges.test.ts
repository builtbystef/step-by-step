import type { Target } from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import { stepBadges, targetHealth } from "./badges";
import type { Step } from "./steps";

const SEALED_OFF =
  "This part of the page is sealed off in a way that automation can't reach later — " +
  "this step will likely fail when the workflow runs.";

const WORKFLOW_DEFAULT_MS = 30_000;

function clicking(target: Target, envelope: Partial<Step> = {}): Step {
  return { id: "1", label: "Click Save", type: "click", payload: { target }, ...envelope } as Step;
}

const FOUND_BY_NAME: Target = { candidates: [{ kind: "role", value: "Save" }] };
const FOUND_BY_POSITION: Target = {
  candidates: [{ kind: "css", value: "div > button:nth-child(2)" }],
};
const SEALED: Target = {
  candidates: [{ kind: "css", value: "div > button" }],
  unsupported: { reason: "closed-shadow-root", warning: SEALED_OFF },
};

describe("how well a Step will find its element", () => {
  it("is well when something the page says out loud was recorded", () => {
    expect(targetHealth(clicking(FOUND_BY_NAME))).toEqual({ state: "ok" });
  });

  it("is fragile when only where the element sat was recorded", () => {
    expect(targetHealth(clicking(FOUND_BY_POSITION))).toEqual({ state: "fragile" });
  });

  it("is unsupported when the recorder said so, and carries what it said", () => {
    expect(targetHealth(clicking(SEALED))).toEqual({
      state: "unsupported",
      warning: SEALED_OFF,
    });
  });

  it("is well for a Step that points at nothing at all", () => {
    const waiting: Step = {
      id: "1",
      label: "Wait",
      type: "wait",
      payload: { mode: "duration", durationMs: 1000 },
    };

    expect(targetHealth(waiting)).toEqual({ state: "ok" });
  });

  it("is not well for a target that has no candidates at all", () => {
    expect(targetHealth(clicking({ candidates: [] }))).toEqual({ state: "fragile" });
  });
});

describe("the badge column", () => {
  it("is empty for a plain Step that is fine", () => {
    expect(stepBadges(clicking(FOUND_BY_NAME), WORKFLOW_DEFAULT_MS)).toEqual([]);
  });

  it("names the envelope a Step carries, and leaves the screenshot toggle to the card", () => {
    const marked = clicking(FOUND_BY_NAME, {
      optional: true,
      disabled: true,
      screenshot: true,
      timeoutMs: 45_000,
    });

    expect(stepBadges(marked, WORKFLOW_DEFAULT_MS).map((badge) => badge.key)).toEqual([
      "optional",
      "off",
      "timeout",
    ]);
  });

  it("says how long an overridden timeout is, against the default it replaces", () => {
    const [badge] = stepBadges(clicking(FOUND_BY_NAME, { timeoutMs: 45_000 }), WORKFLOW_DEFAULT_MS);

    expect(badge?.label).toBe("45 s");
    expect(badge?.title).toContain("30 s");
  });

  it("carries the recorder's own warning on the red badge", () => {
    const badges = stepBadges(clicking(SEALED), WORKFLOW_DEFAULT_MS);

    expect(badges.map((badge) => ({ key: badge.key, tone: badge.tone }))).toEqual([
      { key: "unsupported", tone: "bad" },
    ]);
    expect(badges[0]?.title).toBe(SEALED_OFF);
  });

  it("draws the amber badge for a target only position can find", () => {
    const badges = stepBadges(clicking(FOUND_BY_POSITION), WORKFLOW_DEFAULT_MS);

    expect(badges.map((badge) => ({ key: badge.key, tone: badge.tone }))).toEqual([
      { key: "fragile", tone: "wait" },
    ]);
  });

  it("draws the same amber badge when there is no candidate at all, so the gap is not silent", () => {
    const badges = stepBadges(clicking({ candidates: [] }), WORKFLOW_DEFAULT_MS);

    expect(badges).toEqual([
      {
        key: "fragile",
        label: "no selectors",
        tone: "wait",
        title: "no selectors: pick an element",
      },
    ]);
  });
});
