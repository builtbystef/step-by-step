import { describe, expect, it } from "vitest";

import { refusalMessage } from "./messages";

const REFUSALS = [
  "already_member",
  "already_invited",
  "not_an_admin",
  "not_a_member",
  "invitation_not_found",
];

describe("what a refusal says", () => {
  it("says something different for every refusal the routes can answer with", () => {
    const said = REFUSALS.map((code) => refusalMessage({ code, message: "" }));

    expect(new Set(said).size).toBe(REFUSALS.length);
  });

  it("tells a standing Invitation from a Membership", () => {
    expect(refusalMessage({ code: "already_member", message: "" })).toMatch(/already in/i);
    expect(refusalMessage({ code: "already_invited", message: "" })).toMatch(/Revoke it/);
  });

  it("falls back rather than showing the backend's prose", () => {
    expect(refusalMessage({ code: "teapot", message: "I am a teapot" })).not.toMatch(/teapot/);
    expect(refusalMessage(null)).toBe(refusalMessage({ code: "teapot", message: "" }));
  });
});
