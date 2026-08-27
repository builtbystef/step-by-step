import { describe, expect, it } from "vitest";

import { bindSecretSteps, captureChoices, replacementHint } from "../src/lib/recording.js";

const password = (id) => ({
  id,
  type: "type",
  label: "Type password",
  needsSecret: true,
  payload: { target: { candidates: [] }, value: "" },
});

describe("the saved-login checklist", () => {
  it("starts every distinct domain unchecked at the Organization destination", () => {
    expect(
      captureChoices([
        { domain: "example.co.uk", organization_saved_at: null, personal_saved_at: null },
        { domain: "google.com", organization_saved_at: null, personal_saved_at: null },
      ]),
    ).toEqual([
      {
        domain: "example.co.uk",
        checked: false,
        scope: "organization",
        organizationSavedAt: null,
        personalSavedAt: null,
      },
      {
        domain: "google.com",
        checked: false,
        scope: "organization",
        organizationSavedAt: null,
        personalSavedAt: null,
      },
    ]);
  });

  it("switches the replacement hint with the destination", () => {
    const choice = captureChoices([
      {
        domain: "example.com",
        organization_saved_at: "2026-08-03T09:00:00Z",
        personal_saved_at: "2026-08-07T09:00:00Z",
      },
    ])[0];
    expect(replacementHint(choice, "organization", "en-GB")).toBe(
      "replaces the login saved on 3 Aug",
    );
    expect(replacementHint(choice, "personal", "en-GB")).toBe("replaces your login saved on 7 Aug");
  });
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
