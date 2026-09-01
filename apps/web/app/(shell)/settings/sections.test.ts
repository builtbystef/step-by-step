import type { Account, Role } from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import { SETTINGS_GROUPS, settingsNav } from "./sections";

import { ACCOUNT_PATH, resolveGate } from "../../../lib/gate";

const SIGNED_IN: Account = {
  id: "3f0d7c1e-0000-4000-8000-000000000001",
  email: "ada@example.com",
  display_name: "Ada",
  orgs: [{ id: "3f0d7c1e-0000-4000-8000-000000000002", name: "Acme", role: "member" }],
  invitations: [],
};

const ROLES: Role[] = ["owner", "admin", "member"];

function paths(role: Role): string[] {
  return settingsNav(role).flatMap((group) => group.sections.map((section) => section.path));
}

describe("the section nav", () => {
  it("groups Account with the extension, the Organization's three, and the vault", () => {
    expect(settingsNav("owner")).toEqual([
      {
        label: "Account",
        sections: [
          { label: "Account", path: "/settings/account" },
          { label: "Browser extension", path: "/settings/extension" },
        ],
      },
      {
        label: "Organization",
        sections: [
          { label: "General", path: "/settings/organization" },
          { label: "Members", path: "/settings/organization/members" },
          { label: "Invitations", path: "/settings/organization/invitations" },
        ],
      },
      {
        label: "Vault",
        sections: [
          { label: "Secrets", path: "/settings/secrets" },
          { label: "Saved logins", path: "/settings/logins" },
        ],
      },
    ]);
  });

  it("shows Members to every role — who is in a team is not a secret from it", () => {
    for (const role of ROLES) {
      expect(paths(role)).toContain("/settings/organization/members");
    }
  });

  it("shows Invitations to an owner and an admin, and not to a member", () => {
    expect(paths("owner")).toContain("/settings/organization/invitations");
    expect(paths("admin")).toContain("/settings/organization/invitations");
    expect(paths("member")).not.toContain("/settings/organization/invitations");
  });

  it("offers a member every other section, so hiding one hides only the one", () => {
    const everything = SETTINGS_GROUPS.flatMap((group) =>
      group.sections.map((section) => section.path),
    );

    expect(paths("member")).toEqual(
      everything.filter((path) => path !== "/settings/organization/invitations"),
    );
  });

  it("never offers a section the gate would turn away, and turns away the one it hides", () => {
    for (const role of ROLES) {
      for (const path of paths(role)) {
        expect(resolveGate(SIGNED_IN, role, path)).toEqual({ kind: "render" });
      }
    }

    expect(resolveGate(SIGNED_IN, "member", "/settings/organization/invitations")).toEqual({
      kind: "redirect",
      to: ACCOUNT_PATH,
    });
  });

  it("falls back to a member's nav when no Organization is active to have a role in", () => {
    expect(settingsNav(null)).toEqual(settingsNav("member"));
  });
});
