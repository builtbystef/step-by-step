import { describe, expect, it } from "vitest";

import {
  bindSecretSteps,
  captureChoices,
  fragile,
  navigateStep,
  readPendingRecording,
  replacementHint,
} from "../src/lib/recording.js";

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

describe("a target worth warning about while recording", () => {
  it("is one that could only be placed by its position, or not at all", () => {
    expect(fragile([])).toBe(true);
    expect(fragile([{ kind: "css", value: "#media-container-link" }])).toBe(true);
    expect(
      fragile([
        { kind: "css", value: "div > a" },
        { kind: "css", value: "#one" },
      ]),
    ).toBe(true);
  });

  it("is not one a semantic candidate can find again", () => {
    expect(
      fragile([
        { kind: "label", value: "Rick Astley - Never Gonna Give You Up" },
        { kind: "css", value: "#media-container-link" },
      ]),
    ).toBe(false);
    expect(fragile([{ kind: "role", value: 'button[name="Search"]' }])).toBe(false);
  });
});

describe("the navigate Step", () => {
  it("carries the whole URL and names its host", () => {
    const step = navigateStep("https://www.youtube.com/results?search_query=rick+roll");
    expect(step).toMatchObject({
      type: "navigate",
      label: "Navigate to www.youtube.com",
      optional: false,
      disabled: false,
      screenshot: false,
      payload: { url: "https://www.youtube.com/results?search_query=rick+roll" },
    });
    expect(step.id).toEqual(expect.any(String));
  });
});

describe("the pending recording the app hands over", () => {
  const record = {
    sessionId: "session-1",
    token: "token-1",
    backendOrigin: "https://steps.example.com",
    workflowId: "workflow-1",
    workflowName: "Invoices",
    mode: "record",
    variables: [{ name: "password", secret: true }],
    secrets: [{ id: "secret-1", name: "Portal password" }],
  };

  it("accepts a record session with its Variables and Secrets", () => {
    expect(readPendingRecording(record)).toEqual({
      mode: "record",
      sessionId: "session-1",
      token: "token-1",
      backendOrigin: "https://steps.example.com",
      workflowId: "workflow-1",
      workflowName: "Invoices",
      variables: [{ name: "password", secret: true }],
      secrets: [{ id: "secret-1", name: "Portal password" }],
    });
  });

  it("accepts a Re-pick session scoped to one Step, without Variables", () => {
    expect(
      readPendingRecording({
        sessionId: "session-1",
        token: "token-1",
        backendOrigin: "https://steps.example.com",
        workflowId: "workflow-1",
        workflowName: "Invoices",
        mode: "repick",
        stepId: "step-9",
      }),
    ).toEqual({
      mode: "repick",
      sessionId: "session-1",
      token: "token-1",
      backendOrigin: "https://steps.example.com",
      workflowId: "workflow-1",
      workflowName: "Invoices",
      stepId: "step-9",
    });
  });

  it("refuses a Re-pick without a Step, and a record without its lists", () => {
    expect(readPendingRecording({ ...record, mode: "repick" })).toBeNull();
    expect(readPendingRecording({ ...record, variables: undefined })).toBeNull();
    expect(readPendingRecording({ ...record, mode: "replay" })).toBeNull();
  });
});
