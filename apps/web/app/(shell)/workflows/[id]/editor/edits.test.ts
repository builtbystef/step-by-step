import type { WorkflowDocument } from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import { withStepAdded, withStepDeleted, withStepMoved, withStepReplaced } from "./edits";
import { blankStep, type Step } from "./steps";

/**
 * What the hover tools and the forms do to the Draft: every edit is the whole
 * document again, because that is what a save is.
 *
 * The rule under all of them is the one the document store enforces at the
 * seam — a Step id is minted once and never rewritten — so each of these
 * tests reads the ids back.
 */

function waiting(id: string, ms: number): Step {
  return {
    id,
    label: `Wait ${String(ms)}`,
    type: "wait",
    payload: { mode: "duration", durationMs: ms },
  };
}

const DOCUMENT: WorkflowDocument = {
  steps: [waiting("a", 1000), waiting("b", 2000), waiting("c", 3000)],
  variables: [{ name: "tenant" }],
};

const idsOf = (document: WorkflowDocument) => (document.steps ?? []).map((step) => step.id);

describe("reordering", () => {
  it("swaps a Step with its neighbour and rewrites no id", () => {
    expect(idsOf(withStepMoved(DOCUMENT, "b", "up"))).toEqual(["b", "a", "c"]);
    expect(idsOf(withStepMoved(DOCUMENT, "b", "down"))).toEqual(["a", "c", "b"]);
  });

  it("leaves the list alone at either end", () => {
    expect(idsOf(withStepMoved(DOCUMENT, "a", "up"))).toEqual(["a", "b", "c"]);
    expect(idsOf(withStepMoved(DOCUMENT, "c", "down"))).toEqual(["a", "b", "c"]);
  });

  it("carries the Variables across untouched", () => {
    expect(withStepMoved(DOCUMENT, "b", "up").variables).toEqual(DOCUMENT.variables);
  });
});

describe("deleting", () => {
  it("takes that Step and nothing else", () => {
    expect(idsOf(withStepDeleted(DOCUMENT, "b"))).toEqual(["a", "c"]);
  });
});

describe("adding", () => {
  it("puts the new Step last, under an id no other Step has", () => {
    const grown = withStepAdded(DOCUMENT, blankStep("pause-for-takeover"));
    const ids = idsOf(grown);

    expect(ids.slice(0, 3)).toEqual(["a", "b", "c"]);
    expect(new Set(ids).size).toBe(4);
  });

  it("grows a document that had no Steps at all", () => {
    expect(idsOf(withStepAdded({}, blankStep("wait")))).toHaveLength(1);
  });
});

describe("editing one Step", () => {
  it("puts it back where it was, under the id it already had", () => {
    const edited = withStepReplaced(DOCUMENT, { ...waiting("b", 9000), label: "Wait longer" });

    expect(idsOf(edited)).toEqual(["a", "b", "c"]);
    expect(edited.steps?.[1]?.label).toBe("Wait longer");
    expect(edited.steps?.[0]).toEqual(DOCUMENT.steps?.[0]);
  });
});
