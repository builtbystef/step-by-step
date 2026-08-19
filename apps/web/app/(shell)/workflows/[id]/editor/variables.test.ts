import type { WorkflowDocument } from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import {
  declarationRefusal,
  deletionRefusal,
  secretNames,
  variableRows,
  withVariableDeclared,
  withVariableDeleted,
  withVariableRenamed,
  withLiteralMadeVariable,
  withReferenceInserted,
  withVariableSecret,
} from "./variables";

import { interpolatedValue, type Step } from "./steps";

/**
 * The Variables drawer's decisions, read back without a drawer.
 *
 * Every one of them is a document in and a document out, the way every other
 * edit on this tab is: a Variable is declared inside the Draft document, and
 * the store validates that document as a whole. What the drawer adds is the
 * one question the document does not answer by itself — which Steps use this
 * Variable — and everything the drawer refuses follows from that answer.
 */

function typing(id: string, value: string): Step {
  return {
    id,
    label: "Type it",
    type: "type",
    payload: { target: { candidates: [{ kind: "label", value: "Password" }] }, value },
  };
}

function going(id: string, url: string): Step {
  return { id, label: "Go there", type: "navigate", payload: { url } };
}

describe("what the drawer lists", () => {
  it("gives each declared Variable its name, its secret flag, and the Steps that use it", () => {
    const document: WorkflowDocument = {
      steps: [typing("a", "{{password}}"), going("b", "https://{{tenant}}.example.test")],
      variables: [
        { name: "tenant" },
        { name: "password", secret: true },
        { name: "unused", secret: false },
      ],
    };

    expect(variableRows(document)).toEqual([
      { name: "tenant", secret: false, usedBy: ["b"] },
      { name: "password", secret: true, usedBy: ["a"] },
      { name: "unused", secret: false, usedBy: [] },
    ]);
  });

  it("counts a Step once however often its value names the same Variable", () => {
    const document: WorkflowDocument = {
      steps: [going("a", "https://{{tenant}}.example.test/{{tenant}}/invoices")],
      variables: [{ name: "tenant" }],
    };

    expect(variableRows(document)[0]?.usedBy).toEqual(["a"]);
  });

  it("reads a {{name}} only where a value interpolates one", () => {
    const document: WorkflowDocument = {
      steps: [
        {
          id: "a",
          label: "Choose it",
          type: "select",
          payload: { target: { candidates: [] }, value: "{{country}}" },
        },
      ],
      variables: [{ name: "country" }],
    };

    expect(variableRows(document)[0]?.usedBy).toEqual([]);
  });

  it("lists nothing for a Draft that declares nothing", () => {
    expect(variableRows({})).toEqual([]);
  });
});

describe("declaring a Variable", () => {
  const DECLARED: WorkflowDocument = { steps: [], variables: [{ name: "tenant" }] };

  it("adds it to the Draft document, secret flag and all", () => {
    const grown = withVariableDeclared(DECLARED, { name: "password", secret: true });

    expect(grown.variables).toEqual([{ name: "tenant" }, { name: "password", secret: true }]);
  });

  it("declares into a Draft that holds nothing yet", () => {
    expect(withVariableDeclared({}, { name: "tenant", secret: false }).variables).toEqual([
      { name: "tenant", secret: false },
    ]);
  });

  it("refuses a name the Workflow already declares, because the store would too", () => {
    expect(declarationRefusal(DECLARED, "tenant")).toContain("tenant");
    expect(declarationRefusal(DECLARED, "Tenant")).toBeNull();
  });

  it("refuses a name no {{name}} could ever reach", () => {
    expect(declarationRefusal(DECLARED, "")).not.toBeNull();
    expect(declarationRefusal(DECLARED, "two words")).not.toBeNull();
    expect(declarationRefusal(DECLARED, "1st")).not.toBeNull();
    expect(declarationRefusal(DECLARED, "account_id-2")).toBeNull();
  });
});

describe("deleting a Variable", () => {
  const USED: WorkflowDocument = {
    steps: [typing("a", "{{password}}"), typing("b", "one {{password}} two")],
    variables: [{ name: "password", secret: true }, { name: "spare" }],
  };

  it("is refused while a Step still uses it, and the reason counts the Steps", () => {
    const refusal = deletionRefusal(USED, "password");

    expect(refusal).toContain("2");
    expect(refusal).toContain("password");
  });

  it("goes ahead for one nothing uses", () => {
    expect(deletionRefusal(USED, "spare")).toBeNull();
    expect(withVariableDeleted(USED, "spare").variables).toEqual([
      { name: "password", secret: true },
    ]);
  });

  it("leaves the Steps exactly as they were", () => {
    expect(withVariableDeleted(USED, "spare").steps).toEqual(USED.steps);
  });
});

describe("renaming a Variable", () => {
  const DOCUMENT: WorkflowDocument = {
    steps: [
      typing("a", "{{ password }} and {{password}}"),
      going("b", "https://{{tenant}}.example.test"),
    ],
    variables: [{ name: "password", secret: true }, { name: "tenant" }],
  };

  it("carries every value that reaches for it across to the new name", () => {
    const renamed = withVariableRenamed(DOCUMENT, "password", "secret_key");

    expect(renamed.variables).toEqual([{ name: "secret_key", secret: true }, { name: "tenant" }]);
    expect(interpolatedValue(renamed.steps?.[0] as Step)).toBe("{{secret_key}} and {{secret_key}}");
  });

  it("leaves the values that reach for another Variable alone", () => {
    const renamed = withVariableRenamed(DOCUMENT, "password", "secret_key");

    expect(interpolatedValue(renamed.steps?.[1] as Step)).toBe("https://{{tenant}}.example.test");
  });

  it("keeps every Step id, because a rename is an edit and not a new Step", () => {
    const renamed = withVariableRenamed(DOCUMENT, "password", "secret_key");

    expect((renamed.steps ?? []).map((step) => step.id)).toEqual(["a", "b"]);
  });
});

describe("re-flagging a Variable", () => {
  it("makes a plain Variable secret without touching the values that use it", () => {
    const document: WorkflowDocument = {
      steps: [typing("a", "{{password}}")],
      variables: [{ name: "password" }],
    };

    const flagged = withVariableSecret(document, "password", true);

    expect(flagged.variables).toEqual([{ name: "password", secret: true }]);
    expect(flagged.steps).toEqual(document.steps);
  });
});

describe("inserting a Variable into a value", () => {
  it("puts the {{name}} where the caret was, between the literal text around it", () => {
    expect(withReferenceInserted("https://.example.test", "tenant", 8)).toBe(
      "https://{{tenant}}.example.test",
    );
  });

  it("lets one value carry several Variables and literal text", () => {
    const once = withReferenceInserted("", "tenant", 0);
    const twice = withReferenceInserted(`${once}/`, "year", once.length + 1);

    expect(twice).toBe("{{tenant}}/{{year}}");
  });

  it("appends when the caret sits past the end of the value", () => {
    expect(withReferenceInserted("id-", "account", 99)).toBe("id-{{account}}");
  });
});

describe("making a Variable out of a value a recording captured", () => {
  const RECORDED: WorkflowDocument = {
    steps: [typing("a", "acme-corp"), typing("b", "acme-corp")],
    variables: [],
  };

  it("declares it and leaves a {{name}} where the literal text was", () => {
    const converted = withLiteralMadeVariable(
      RECORDED,
      "a",
      { name: "tenant", secret: false },
      { from: 0, to: "acme-corp".length },
    );

    expect(converted.variables).toEqual([{ name: "tenant", secret: false }]);
    expect(interpolatedValue(converted.steps?.[0] as Step)).toBe("{{tenant}}");
  });

  it("converts the run of text that was picked, and keeps the rest of the value", () => {
    const document: WorkflowDocument = { steps: [typing("a", "acme-corp/2026")], variables: [] };

    const converted = withLiteralMadeVariable(
      document,
      "a",
      { name: "tenant", secret: false },
      { from: 0, to: 9 },
    );

    expect(interpolatedValue(converted.steps?.[0] as Step)).toBe("{{tenant}}/2026");
  });

  it("touches no other Step, even one that holds the same literal", () => {
    const converted = withLiteralMadeVariable(
      RECORDED,
      "a",
      { name: "tenant", secret: false },
      { from: 0, to: 9 },
    );

    expect(converted.steps?.[1]).toEqual(RECORDED.steps?.[1]);
  });

  it("carries the secret flag, which is what decides masking later", () => {
    const converted = withLiteralMadeVariable(
      RECORDED,
      "a",
      { name: "password", secret: true },
      { from: 0, to: 9 },
    );

    expect(converted.variables).toEqual([{ name: "password", secret: true }]);
  });
});

describe("which Variables are secret", () => {
  it("is what a pill is drawn from, and it is the flag rather than the name", () => {
    const document: WorkflowDocument = {
      variables: [{ name: "password", secret: true }, { name: "tenant" }, { name: "secret_note" }],
    };

    expect(secretNames(document)).toEqual(new Set(["password"]));
  });
});
