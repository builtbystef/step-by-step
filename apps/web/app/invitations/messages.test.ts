import type { Account } from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import { manageableOrgs, offerSentence, refusalMessage } from "./messages";

/**
 * The screen's two decisions, tested where they are made: what a refusal
 * says, and which Organizations offer a panel at all.
 */

const REFUSALS = [
  "already_member",
  "already_invited",
  "not_an_admin",
  "not_a_member",
  "invitation_not_found",
];

function account(...roles: Account["orgs"][number]["role"][]): Account {
  return {
    id: "3f0d7c1e-0000-4000-8000-000000000001",
    email: "ada@example.com",
    display_name: null,
    orgs: roles.map((role, index) => ({
      id: `3f0d7c1e-0000-4000-8000-00000000000${String(index + 2)}`,
      name: role,
      role,
    })),
    invitations: [],
  };
}

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

describe("which Organizations get a panel", () => {
  it("gives one to an owner and to an admin, and none to a member", () => {
    expect(manageableOrgs(account("owner", "admin", "member")).map((org) => org.role)).toEqual([
      "owner",
      "admin",
    ]);
  });

  it("gives none to a visitor with no identity yet", () => {
    expect(manageableOrgs(null)).toEqual([]);
  });
});

describe("what the banner says", () => {
  it("names the Organization and the role, in English", () => {
    expect(offerSentence({ id: "x", org_name: "Acme", role: "admin" })).toBe(
      "Acme invited you to join as an admin.",
    );
    expect(offerSentence({ id: "x", org_name: "Acme", role: "member" })).toBe(
      "Acme invited you to join as a member.",
    );
  });
});
