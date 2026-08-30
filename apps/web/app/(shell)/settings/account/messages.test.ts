import type { Account, OrganizationMembership } from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import {
  emailConfirms,
  endingConsequence,
  ownedOrganizations,
  refusalMessage,
  soleOwnerExplanation,
} from "./messages";

const REFUSALS = ["sole_owner", "confirmation_mismatch"];

function org(name: string, role: OrganizationMembership["role"]): OrganizationMembership {
  return { id: `id-${name}`, name, role };
}

function account(...orgs: OrganizationMembership[]): Account {
  return {
    id: "3f0d7c1e-0000-4000-8000-000000000001",
    email: "Ada@Example.com",
    display_name: null,
    orgs,
    invitations: [],
  };
}

describe("what a refusal says", () => {
  it("says something different for every refusal the route can answer with", () => {
    const said = REFUSALS.map((code) => refusalMessage({ code, message: "" }));

    expect(new Set(said).size).toBe(REFUSALS.length);
  });

  it("falls back rather than showing the backend's prose", () => {
    expect(refusalMessage({ code: "teapot", message: "I am a teapot" })).not.toMatch(/teapot/);
    expect(refusalMessage(null)).toBe(refusalMessage({ code: "teapot", message: "" }));
  });
});

describe("when the typed address means it", () => {
  it("takes the address in any case, because the identity is the mailbox", () => {
    expect(emailConfirms("ada@example.com", "Ada@Example.com")).toBe(true);
    expect(emailConfirms("  Ada@Example.com  ", "Ada@Example.com")).toBe(true);
  });

  it("takes nothing else", () => {
    expect(emailConfirms("", "Ada@Example.com")).toBe(false);
    expect(emailConfirms("ada@example.co", "Ada@Example.com")).toBe(false);
    expect(emailConfirms("grace@example.com", "Ada@Example.com")).toBe(false);
  });
});

describe("what still holds the account here", () => {
  it("is every Organization this account owns, and nothing it merely belongs to", () => {
    const owned = ownedOrganizations(account(org("Ada's", "owner"), org("Grace's", "member")));

    expect(owned.map((held) => held.name)).toEqual(["Ada's"]);
  });

  it("holds nothing when the visitor is not known yet", () => {
    expect(ownedOrganizations(null)).toEqual([]);
  });

  it("names each one, and both ways out of it", () => {
    const said = soleOwnerExplanation([org("Ada's", "owner"), org("Bell Labs", "owner")]);

    expect(said).toMatch(/Ada's/);
    expect(said).toMatch(/Bell Labs/);
    expect(said).toMatch(/hand/i);
    expect(said).toMatch(/delete|end/i);
  });
});

describe("what ending the account takes with it", () => {
  it("says that it reaches every browser and that nothing comes back", () => {
    const said = endingConsequence();

    expect(said).toMatch(/session|browser/i);
    expect(said).toMatch(/cannot be undone|permanent|forever/i);
  });
});
