import { describe, expect, it } from "vitest";

import { readRefusal, saveRefusal } from "./messages";

describe("a refused save", () => {
  it("names the Step the duplicate id is on, in the backend's own words", () => {
    const said = saveRefusal({
      code: "duplicate_step_id",
      message: "two Steps carry the id 7b1e2f0c-0000-4000-8000-000000000000",
    });

    expect(said).toContain("7b1e2f0c-0000-4000-8000-000000000000");
    expect(said).toContain("not saved");
  });

  it("names the Variable a value reaches for and the document does not declare", () => {
    const said = saveRefusal({
      code: "undeclared_variable",
      message: "a Step value references {{tenant}}, which this Workflow does not declare",
    });

    expect(said).toContain("{{tenant}}");
  });

  it("still says something when the refusal is one this screen has never seen", () => {
    expect(saveRefusal({ code: "teapot", message: "" })).toBe(saveRefusal("a network error"));
    expect(saveRefusal(undefined)).not.toBe("");
  });

  it("says the Draft is untouched, because a refused save changes nothing", () => {
    for (const code of ["duplicate_step_id", "undeclared_variable", "malformed_payload"]) {
      expect(saveRefusal({ code, message: "" })).toContain("not saved");
    }
  });
});

describe("a document that will not load", () => {
  it("says a Version that is not here is not here, and where the real ones are", () => {
    const said = readRefusal({ code: "version_not_found", message: "this Workflow has no v9" });

    expect(said).toContain("Version");
    expect(said).not.toContain("not saved");
  });

  it("never says a save failed, because nothing was being saved", () => {
    expect(readRefusal("a network error")).not.toContain("saved");
    expect(readRefusal({ code: "workflow_not_found", message: "" })).not.toContain("saved");
  });
});
