import type { Target } from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import {
  ADDABLE_STEP_TYPES,
  STEP_TYPE_LABELS,
  blankStep,
  targetsOf,
  type Step,
  type StepType,
} from "./steps";

/**
 * What the editor knows about a Step before it renders one: what each of the
 * eight types is called, which of them a person can add by hand, and where a
 * Step keeps the elements it points at.
 */

const A_TARGET: Target = { candidates: [{ kind: "css", value: "#save" }] };

const EVERY_TYPE: StepType[] = [
  "navigate",
  "click",
  "type",
  "select",
  "download",
  "extract",
  "wait",
  "pause-for-takeover",
];

describe("the eight step types", () => {
  it("each carry a name a person reads, and no two share one", () => {
    const labels = EVERY_TYPE.map((type) => STEP_TYPE_LABELS[type]);

    expect(new Set(labels).size).toBe(EVERY_TYPE.length);
    expect(labels).not.toContain("pause-for-takeover");
  });
});

describe("where a Step points", () => {
  it("finds the target of every type that has one", () => {
    const click: Step = {
      id: "1",
      label: "Click Save",
      type: "click",
      payload: { target: A_TARGET },
    };

    expect(targetsOf(click)).toEqual([A_TARGET]);
  });

  it("finds none on the types that point at nothing", () => {
    const navigate: Step = {
      id: "1",
      label: "Go to the invoices",
      type: "navigate",
      payload: { url: "https://example.test" },
    };
    const waiting: Step = {
      id: "2",
      label: "Wait 5 s",
      type: "wait",
      payload: { mode: "duration", durationMs: 5000 },
    };

    expect(targetsOf(navigate)).toEqual([]);
    expect(targetsOf(waiting)).toEqual([]);
  });

  it("counts a takeover's success check, which is the element that ends the pause", () => {
    const pause: Step = {
      id: "1",
      label: "Solve the captcha",
      type: "pause-for-takeover",
      payload: { message: "Solve the captcha", successCheck: A_TARGET },
    };
    const manual: Step = { id: "2", label: "Take over", type: "pause-for-takeover", payload: {} };

    expect(targetsOf(pause)).toEqual([A_TARGET]);
    expect(targetsOf(manual)).toEqual([]);
  });
});

describe("a Step added in the editor", () => {
  it("is minted under an id of its own, every time", () => {
    const one = blankStep("wait");
    const other = blankStep("wait");

    expect(one.id).not.toBe(other.id);
    expect(one.id).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("arrives with the type it was asked for and a label that says what it is", () => {
    expect(blankStep("pause-for-takeover").type).toBe("pause-for-takeover");
    expect(blankStep("navigate").label).not.toBe("");
  });

  it("is offered only for the types the editor can finish", () => {
    for (const type of ADDABLE_STEP_TYPES) {
      expect(targetsOf(blankStep(type))).toEqual([]);
    }
  });

  it("offers the two types that are only ever added by hand", () => {
    expect(ADDABLE_STEP_TYPES).toContain("wait");
    expect(ADDABLE_STEP_TYPES).toContain("pause-for-takeover");
  });
});
