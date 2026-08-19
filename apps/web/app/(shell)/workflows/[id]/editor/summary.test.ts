import type { Target } from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import type { Step } from "./steps";
import { sentenceOf, summarize, targetToken } from "./summary";

/**
 * The line under a card's label: the Step as a sentence, with the Variables
 * it interpolates and the element it points at kept apart from the words
 * around them, so the card can draw a pill and a token rather than braces.
 *
 * The worked example is the spec's own: "Type {{password}} into Password".
 */

const PASSWORD_FIELD: Target = {
  candidates: [
    { kind: "label", value: "Password" },
    { kind: "css", value: "#login > input:nth-child(2)" },
  ],
};

describe("a Step as a sentence", () => {
  it("reads a type Step as its value going into its field", () => {
    const step: Step = {
      id: "1",
      label: "Enter the password",
      type: "type",
      payload: { target: PASSWORD_FIELD, value: "{{password}}" },
    };

    expect(summarize(step)).toEqual([
      { kind: "text", text: "Type " },
      { kind: "variable", name: "password" },
      { kind: "text", text: " into " },
      { kind: "target", text: "Password", machine: false },
    ]);
  });

  it("keeps the literal text a value mixes with its Variables", () => {
    const step: Step = {
      id: "1",
      label: "Go to the tenant",
      type: "navigate",
      payload: { url: "https://{{tenant}}.example.test/invoices" },
    };

    expect(sentenceOf(step)).toBe("Go to https://{{tenant}}.example.test/invoices");
    expect(summarize(step).filter((part) => part.kind === "variable")).toEqual([
      { kind: "variable", name: "tenant" },
    ]);
  });

  it("reads a {{name}} in a value nothing interpolates as the text it is", () => {
    const step: Step = {
      id: "1",
      label: "Choose the country",
      type: "select",
      payload: { target: { candidates: [{ kind: "label", value: "Country" }] }, value: "{{DE}}" },
    };

    expect(summarize(step)).toEqual([
      { kind: "text", text: "Choose {{DE}} in " },
      { kind: "target", text: "Country", machine: false },
    ]);
  });

  it("says what each of the remaining types does", () => {
    const target: Target = { candidates: [{ kind: "role", value: "Save" }] };

    expect(sentenceOf({ id: "1", label: "", type: "click", payload: { target } })).toBe(
      "Click Save",
    );
    expect(sentenceOf({ id: "2", label: "", type: "download", payload: { target } })).toBe(
      "Download the file from Save",
    );
    expect(
      sentenceOf({
        id: "3",
        label: "",
        type: "extract",
        payload: { target, mode: "scalar", outputName: "total", attribute: "value" },
      }),
    ).toBe("Extract total from Save, its value attribute");
    expect(
      sentenceOf({
        id: "4",
        label: "",
        type: "extract",
        payload: {
          target,
          mode: "list",
          outputName: "rows",
          fields: [{ name: "price", subSelector: ".price" }],
        },
      }),
    ).toBe("Extract a list of rows from Save");
    expect(
      sentenceOf({
        id: "5",
        label: "",
        type: "wait",
        payload: { mode: "duration", durationMs: 5000 },
      }),
    ).toBe("Wait 5 s");
    expect(
      sentenceOf({ id: "6", label: "", type: "wait", payload: { mode: "element", target } }),
    ).toBe("Wait for Save to appear");
    expect(
      sentenceOf({
        id: "7",
        label: "",
        type: "pause-for-takeover",
        payload: { message: "Solve the captcha" },
      }),
    ).toBe("Pause and ask: “Solve the captcha”");
    expect(sentenceOf({ id: "8", label: "", type: "pause-for-takeover", payload: {} })).toBe(
      "Pause for a person to take over",
    );
  });
});

describe("the token a sentence names an element by", () => {
  it("takes the best candidate a person can read over a better-ranked machine one", () => {
    expect(targetToken(PASSWORD_FIELD)).toEqual({ text: "Password", machine: false });
  });

  it("falls back to the selector itself, and says that it is one", () => {
    const positional: Target = { candidates: [{ kind: "css", value: "#login > input" }] };

    expect(targetToken(positional)).toEqual({ text: "#login > input", machine: true });
  });

  it("says so plainly when a target has no way of being found at all", () => {
    expect(targetToken({ candidates: [] })).toEqual({ text: "the element", machine: false });
  });
});
