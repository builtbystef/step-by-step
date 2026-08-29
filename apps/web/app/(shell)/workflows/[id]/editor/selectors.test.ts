import type { SelectorCandidate, Target } from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import { targetHealth } from "./badges";
import {
  CANDIDATE_KINDS,
  candidateKindTone,
  candidateUniqueness,
  selectorHealthCopy,
  selectorHealthTone,
  withCandidateAdded,
  withCandidateRemoved,
  withCandidateMovedToTop,
  withCandidates,
  repickRefusal,
} from "./selectors";
import type { Step } from "./steps";

/**
 * The selector panel's decisions, read back without a DOM: how healthy a
 * target is, in the spec's own words; what the candidate tools do to the
 * list; and the one sentence that refuses Re-pick while the editor is dirty.
 */

const TESTID: SelectorCandidate = { kind: "testid", value: "save" };
const ROLE: SelectorCandidate = { kind: "role", value: 'button[name="Save"]' };
const CSS: SelectorCandidate = { kind: "css", value: "div > button:nth-child(2)" };

const SEALED_OFF =
  "This part of the page is sealed off in a way that automation can't reach later — " +
  "this step will likely fail when the workflow runs.";

function clicking(target: Target): Step {
  return { id: "1", label: "Click Save", type: "click", payload: { target } };
}

describe("the collapsed health badge", () => {
  it("says how many verified ways there are, in the spec's words", () => {
    const target: Target = { candidates: [TESTID, ROLE, CSS] };

    expect(selectorHealthCopy(targetHealth(clicking(target)), target.candidates.length)).toBe(
      "3 ways to find it — verified when recorded",
    );
    expect(selectorHealthTone(targetHealth(clicking(target)), target.candidates.length)).toBe("ok");
  });

  it("says 1 way, not 1 ways", () => {
    const target: Target = { candidates: [TESTID] };

    expect(selectorHealthCopy(targetHealth(clicking(target)), 1)).toBe(
      "1 way to find it — verified when recorded",
    );
  });

  it("says fragile in the spec's words when only position was recorded", () => {
    const target: Target = { candidates: [CSS] };

    expect(selectorHealthCopy(targetHealth(clicking(target)), 1)).toBe(
      "fragile — only position-based selectors",
    );
    expect(selectorHealthTone(targetHealth(clicking(target)), 1)).toBe("wait");
  });

  it("carries the recorder's own warning when the target is unsupported", () => {
    const target: Target = {
      candidates: [CSS],
      unsupported: { reason: "closed-shadow-root", warning: SEALED_OFF },
    };

    expect(selectorHealthCopy(targetHealth(clicking(target)), 1)).toBe(SEALED_OFF);
    expect(selectorHealthTone(targetHealth(clicking(target)), 1)).toBe("bad");
  });

  it("asks to pick an element when there is no candidate at all", () => {
    const target: Target = { candidates: [] };

    expect(selectorHealthCopy(targetHealth(clicking(target)), 0)).toBe(
      "no selectors — pick an element",
    );
    expect(selectorHealthTone(targetHealth(clicking(target)), 0)).toBe("wait");
  });
});

describe("a candidate row", () => {
  it("marks a CSS candidate as the weak, position-based kind", () => {
    expect(candidateKindTone("css")).toBe("wait");
    expect(candidateKindTone("testid")).toBe("accent");
    expect(candidateKindTone("role")).toBe("accent");
  });

  it("names uniqueness as unique, because every persisted candidate was verified at capture", () => {
    expect(candidateUniqueness(TESTID)).toEqual({
      label: "unique",
      title: "Matched exactly one element at record time",
    });
    expect(candidateUniqueness(CSS)).toEqual({
      label: "unique",
      title: "Matched exactly one element at record time",
    });
  });

  it("offers every kind a person can add by hand, in rank order", () => {
    expect(CANDIDATE_KINDS).toEqual([
      "testid",
      "role",
      "placeholder",
      "label",
      "alt",
      "text",
      "title",
      "css",
    ]);
  });
});

describe("hand-editing the candidate list", () => {
  const ranked = [TESTID, ROLE, CSS];

  it("moves one to the top and keeps the rest in their order", () => {
    expect(withCandidateMovedToTop(ranked, 2)).toEqual([CSS, TESTID, ROLE]);
  });

  it("leaves the list alone when that candidate is already first", () => {
    expect(withCandidateMovedToTop(ranked, 0)).toEqual(ranked);
  });

  it("leaves the list alone for an index that is not there", () => {
    expect(withCandidateMovedToTop(ranked, 9)).toEqual(ranked);
    expect(withCandidateRemoved(ranked, 9)).toEqual(ranked);
  });

  it("removes one and does not rewrite the others", () => {
    expect(withCandidateRemoved(ranked, 1)).toEqual([TESTID, CSS]);
  });

  it("adds one at the end, the weakest rank until it is moved", () => {
    const extra: SelectorCandidate = { kind: "label", value: "Save" };
    expect(withCandidateAdded(ranked, extra)).toEqual([TESTID, ROLE, CSS, extra]);
  });

  it("replaces only the candidate list on a target, leaving frame and unsupported", () => {
    const target: Target = {
      candidates: [CSS],
      frame: [{ index: 0, name: "main" }],
      unsupported: { reason: "closed-shadow-root", warning: SEALED_OFF },
    };

    expect(withCandidates(target, [TESTID, ROLE])).toEqual({
      ...target,
      candidates: [TESTID, ROLE],
    });
  });
});

describe("starting a Re-pick", () => {
  it("is refused while the editor has unsaved edits, in one sentence", () => {
    expect(repickRefusal(true)).toBe("Save or discard your editor changes before re-picking.");
    expect(repickRefusal(false)).toBeNull();
  });
});
