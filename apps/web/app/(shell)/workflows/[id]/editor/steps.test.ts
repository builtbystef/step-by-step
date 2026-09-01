import type { Target } from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import { targetHealth } from "./badges";
import { selectorHealthCopy } from "./selectors";
import {
  ADDABLE_STEP_TYPES,
  STEP_TYPE_LABELS,
  blankStep,
  interpolatedValue,
  targetsOf,
  withInterpolatedValue,
  withWaitMode,
  type Step,
  type StepType,
} from "./steps";

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

const TARGETING_TYPES = ["click", "type", "select", "download", "extract"] as const;

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
    expect(blankStep("click").label).toBe(STEP_TYPE_LABELS.click);
  });

  it("offers all eight types, in the order a person reads them", () => {
    expect(ADDABLE_STEP_TYPES).toEqual(EVERY_TYPE);
  });

  it("a targeting Step arrives with an empty candidate list, never a silent one", () => {
    for (const type of TARGETING_TYPES) {
      const step = blankStep(type);
      const [target] = targetsOf(step);

      expect(target?.candidates).toEqual([]);
      expect(targetHealth(step).state).not.toBe("ok");
      expect(selectorHealthCopy(targetHealth(step), 0)).toBe("no selectors: pick an element");
    }
  });
});

describe("switching a wait", () => {
  it("lands in element mode on an empty target the hand-edit panel can fill", () => {
    const waiting = withWaitMode(blankStep("wait"), "element");

    expect(waiting.type).toBe("wait");
    expect(waiting.payload).toEqual({ mode: "element", target: { candidates: [] } });
    expect(targetHealth(waiting).state).not.toBe("ok");
    expect(selectorHealthCopy(targetHealth(waiting), 0)).toBe("no selectors: pick an element");
  });

  it("keeps the Step's id when the mode changes", () => {
    const original = blankStep("wait");
    const waiting = withWaitMode(original, "element");
    const back = withWaitMode(waiting, "duration");

    expect(waiting.id).toBe(original.id);
    expect(back.id).toBe(original.id);
    expect(back.payload).toEqual({ mode: "duration", durationMs: 1000 });
    expect(targetsOf(back)).toEqual([]);
  });

  it("leaves a wait already in that mode alone, including its target", () => {
    const aimed: Step = {
      id: "1",
      label: "Wait",
      type: "wait",
      payload: { mode: "element", target: A_TARGET },
    };

    expect(withWaitMode(aimed, "element")).toEqual(aimed);
    expect(withWaitMode(blankStep("wait"), "duration").payload).toEqual({
      mode: "duration",
      durationMs: 1000,
    });
  });
});

describe("the value a Step interpolates Variables into", () => {
  it("is the URL of a navigate and the value of a type, and nothing else", () => {
    const going: Step = {
      id: "1",
      label: "",
      type: "navigate",
      payload: { url: "https://a.test" },
    };
    const choosing: Step = {
      id: "2",
      label: "",
      type: "select",
      payload: { target: A_TARGET, value: "Germany" },
    };

    expect(interpolatedValue(going)).toBe("https://a.test");
    expect(
      interpolatedValue({
        id: "3",
        label: "",
        type: "type",
        payload: { target: A_TARGET, value: "x" },
      }),
    ).toBe("x");
    expect(interpolatedValue(choosing)).toBeNull();
  });

  it("is written back into the payload the type keeps it in", () => {
    const typed: Step = {
      id: "1",
      label: "",
      type: "type",
      payload: { target: A_TARGET, value: "x" },
    };

    const written = withInterpolatedValue(typed, "{{password}}");

    expect(interpolatedValue(written)).toBe("{{password}}");
    expect(written.id).toBe("1");
  });
});
