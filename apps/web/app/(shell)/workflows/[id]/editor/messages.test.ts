import { describe, expect, it } from "vitest";

import { saveRefusal } from "./messages";

/**
 * What the editor says when the Draft API refuses a save.
 *
 * The document store validates the whole document, so a refusal is about one
 * Step among a hundred — and the only thing that says which one is the
 * message the backend wrote. A screen that swallowed it would leave the user
 * with a list to search by hand.
 */

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
