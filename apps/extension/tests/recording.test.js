import { describe, expect, it } from "vitest";

import { bindSecretSteps } from "../src/lib/recording.js";

const password = (id) => ({
  id,
  type: "type",
  label: "Type password",
  needsSecret: true,
  payload: { target: { candidates: [] }, value: "" },
});

describe("binding password Steps before finalizing", () => {
  it("binds every marker and preserves existing Variables", () => {
    expect(
      bindSecretSteps(
        [password("one"), password("two")],
        [
          { stepId: "one", name: "existing" },
          { stepId: "two", name: "new_secret" },
        ],
        [
          { name: "plain", secret: false },
          { name: "existing", secret: true },
        ],
      ),
    ).toEqual({
      steps: [
        {
          id: "one",
          type: "type",
          label: "Type password",
          payload: { target: { candidates: [] }, value: "{{existing}}" },
        },
        {
          id: "two",
          type: "type",
          label: "Type password",
          payload: { target: { candidates: [] }, value: "{{new_secret}}" },
        },
      ],
      variables: [
        { name: "plain", secret: false },
        { name: "existing", secret: true },
        { name: "new_secret", secret: true },
      ],
    });
  });

  it.each([
    ["an unbound Step", [], "Bind every password Step before saving."],
    [
      "an invalid new name",
      [{ stepId: "one", name: "not a name" }],
      "Choose a valid Variable name.",
    ],
    [
      "an existing plain Variable",
      [{ stepId: "one", name: "plain" }],
      "A password Step needs a secret Variable.",
    ],
  ])("refuses %s", (_case, bindings, message) => {
    expect(() => bindSecretSteps([password("one")], bindings, [{ name: "plain" }])).toThrow(
      message,
    );
  });
});
