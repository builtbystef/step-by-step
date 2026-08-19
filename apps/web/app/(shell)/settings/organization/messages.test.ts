import type { Member, Role } from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import {
  endingConsequence,
  mayEnd,
  mayRename,
  memberControls,
  memberLabel,
  nameConfirms,
  refusalMessage,
  transferConsequence,
} from "./messages";

/**
 * The screen's decisions, tested where they are made: what a refusal says, and
 * which control each row of the member list offers whom.
 */

const REFUSALS = [
  "not_a_member",
  "not_an_admin",
  "not_the_owner",
  "is_owner",
  "member_not_found",
  "confirmation_mismatch",
];

const ADA = "3f0d7c1e-0000-4000-8000-000000000001";
const GRACE = "3f0d7c1e-0000-4000-8000-000000000002";

function row(user_id: string, role: Role, display_name: string | null = null): Member {
  return {
    user_id,
    email: `${user_id === ADA ? "ada" : "grace"}@example.com`,
    display_name,
    role,
    joined_at: "2026-08-19T10:00:00Z",
  };
}

describe("what a refusal says", () => {
  it("says something different for every refusal the routes can answer with", () => {
    const said = REFUSALS.map((code) => refusalMessage({ code, message: "" }));

    expect(new Set(said).size).toBe(REFUSALS.length);
  });

  it("falls back rather than showing the backend's prose", () => {
    expect(refusalMessage({ code: "teapot", message: "I am a teapot" })).not.toMatch(/teapot/);
    expect(refusalMessage(null)).toBe(refusalMessage({ code: "teapot", message: "" }));
  });
});

describe("who may rename the Organization", () => {
  it("is the owner and the admins, and not a member", () => {
    expect(mayRename("owner")).toBe(true);
    expect(mayRename("admin")).toBe(true);
    expect(mayRename("member")).toBe(false);
  });
});

describe("what one row offers", () => {
  it("offers nothing at all on the owner's row", () => {
    const viewer = { role: "owner" as Role, userId: ADA };

    expect(memberControls(viewer, row(ADA, "owner"))).toEqual({
      changeRole: false,
      remove: false,
      leave: false,
      makeOwner: false,
    });
  });

  it("offers an admin and a member the way out of their own row", () => {
    for (const role of ["admin", "member"] as Role[]) {
      expect(memberControls({ role, userId: GRACE }, row(GRACE, role)).leave).toBe(true);
    }
  });

  it("offers a member no control over anybody else", () => {
    expect(memberControls({ role: "member", userId: GRACE }, row(ADA, "admin"))).toEqual({
      changeRole: false,
      remove: false,
      leave: false,
      makeOwner: false,
    });
  });

  it("offers an admin the role and the removal, and the transfer to nobody but the owner", () => {
    const asAdmin = memberControls({ role: "admin", userId: ADA }, row(GRACE, "member"));
    const asOwner = memberControls({ role: "owner", userId: ADA }, row(GRACE, "member"));

    expect(asAdmin).toEqual({ changeRole: true, remove: true, leave: false, makeOwner: false });
    expect(asOwner.makeOwner).toBe(true);
  });
});

describe("how a person is named", () => {
  it("keeps the address, and adds the name when there is one", () => {
    expect(memberLabel(row(GRACE, "member"))).toBe("grace@example.com");
    expect(memberLabel(row(GRACE, "member", "Grace"))).toBe("Grace (grace@example.com)");
  });
});

describe("what the transfer says before it happens", () => {
  it("names both halves: who takes it, and what the asker becomes", () => {
    const said = transferConsequence(row(GRACE, "member"), "Acme");

    expect(said).toMatch(/grace@example\.com becomes the owner of Acme/);
    expect(said).toMatch(/you become an admin/);
  });
});

describe("who may end the Organization", () => {
  it("is the owner alone", () => {
    expect(mayEnd("owner")).toBe(true);
    expect(mayEnd("admin")).toBe(false);
    expect(mayEnd("member")).toBe(false);
  });
});

describe("when the typed name means it", () => {
  it("takes the name, and the whitespace a paste carries with it", () => {
    expect(nameConfirms("Bell Labs", "Bell Labs")).toBe(true);
    expect(nameConfirms("  Bell Labs  ", "Bell Labs")).toBe(true);
  });

  it("takes nothing else — reading the name off the screen is the act", () => {
    expect(nameConfirms("", "Bell Labs")).toBe(false);
    expect(nameConfirms("bell labs", "Bell Labs")).toBe(false);
    expect(nameConfirms("Bell Lab", "Bell Labs")).toBe(false);
  });
});

describe("what ending the Organization takes with it", () => {
  it("names it, says the work goes, and says the people keep their accounts", () => {
    const said = endingConsequence("Bell Labs");

    expect(said).toMatch(/Bell Labs/);
    expect(said).toMatch(/member|Membership/i);
    expect(said).toMatch(/account/i);
    expect(said).toMatch(/cannot be undone|permanent|forever/i);
  });
});
