import { describe, expect, it } from "vitest";

import type { Variable } from "@step-by-step/api-client";

import { COPY } from "../../../../../lib/copy";
import { refusalToRun } from "../../draft-state";

import { testRunBody, testRunFields, testRunRefusal } from "./test-run";

/**
 * The test-run action: a modal over the Draft, never the published Version.
 *
 * One field per declared Variable, secret ones masked, and the shared
 * publish-first sentence has nothing to say here — a never-published
 * Workflow can still verify its Draft.
 */

const PLAIN: Variable = { name: "customer", secret: false };
const SECRET: Variable = { name: "password", secret: true, secretName: "vault-password" };

describe("the test-run form", () => {
  it("asks for a value per declared Variable, and marks secret ones masked", () => {
    expect(testRunFields([PLAIN, SECRET])).toEqual([
      { name: "customer", secret: false },
      { name: "password", secret: true },
    ]);
  });

  it("sends the typed values as a test Run and nothing for a secret Variable", () => {
    const fields = testRunFields([PLAIN, SECRET]);

    expect(testRunBody({ customer: "Ada", password: "do-not-store" }, fields)).toEqual({
      test: true,
      variables: { customer: "Ada" },
    });
  });
});

describe("what refuses a test run", () => {
  it("is never the shared publish-first sentence, even with nothing published", () => {
    expect(refusalToRun("never-published")).toBe(COPY.noPublishedVersion);
    expect(testRunRefusal("never-published", false)).toBeNull();
    expect(testRunRefusal("in-sync", false)).toBeNull();
    expect(testRunRefusal("unpublished-changes", false)).toBeNull();
  });

  it("is refused while the editor has unsaved changes", () => {
    expect(testRunRefusal("never-published", true)).toBe(
      "Save or discard your editor changes before a test run.",
    );
  });
});
