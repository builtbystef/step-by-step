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
          {
            stepId: "one",
            name: "existing",
            secret: { id: "secret-1", name: "Existing password" },
          },
          {
            stepId: "two",
            name: "new_secret",
            secret: { id: "secret-2", name: "New password" },
          },
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
        {
          name: "existing",
          secret: true,
          secretId: "secret-1",
          secretName: "Existing password",
        },
        {
          name: "new_secret",
          secret: true,
          secretId: "secret-2",
          secretName: "New password",
        },
      ],
    });
  });

  it.each([
    ["an unbound Step", [], "Bind every password Step before saving."],
    [
      "an invalid new name",
      [
        {
          stepId: "one",
          name: "not a name",
          secret: { id: "secret-1", name: "Password" },
        },
      ],
      "Choose a valid Variable name.",
    ],
    [
      "an existing plain Variable",
      [
        {
          stepId: "one",
          name: "plain",
          secret: { id: "secret-1", name: "Password" },
        },
      ],
      "A password Step needs a secret Variable.",
    ],
  ])("refuses %s", (_case, bindings, message) => {
    expect(() => bindSecretSteps([password("one")], bindings, [{ name: "plain" }])).toThrow(
      message,
    );
  });

  it("requires a vault Secret and can bind an existing secret Variable", () => {
    expect(() =>
      bindSecretSteps(
        [password("one")],
        [{ stepId: "one", name: "password" }],
        [{ name: "password", secret: true }],
      ),
    ).toThrow("Choose or create a Secret for every password Step.");

    expect(
      bindSecretSteps(
        [password("one")],
        [
          {
            stepId: "one",
            name: "password",
            secret: { id: "vault-id", name: "Portal password" },
          },
        ],
        [{ name: "password", secret: true }],
      ).variables,
    ).toEqual([
      {
        name: "password",
        secret: true,
        secretId: "vault-id",
        secretName: "Portal password",
      },
    ]);
  });
});
