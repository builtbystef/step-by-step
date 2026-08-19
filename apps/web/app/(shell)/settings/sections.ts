import type { Role } from "@step-by-step/api-client";

/**
 * Settings' left section nav: every panel the app has, and which of them a
 * role is offered.
 *
 * The Organization's sections live here rather than beside the work, so that a
 * one-person Organization is one section of one screen and still one click
 * from anywhere.
 *
 * The role rule is the backend's, said again for one reason: a section whose
 * every control would answer 403 is worse than no section. It is not the
 * guard — the guard is the backend's, and the route gate is what turns a
 * refused address away.
 */

export type SettingsSection = {
  label: string;
  path: string;
};

export type SettingsGroup = {
  /** The heading above the group, or nothing where the sections stand alone. */
  label: string | null;
  sections: SettingsSection[];
};

/** The one section an owner and an admin have that a member does not. */
const INVITATIONS_PATH = "/settings/organization/invitations";

/** Every section there is, in the order the nav renders them. */
export const SETTINGS_GROUPS: readonly SettingsGroup[] = [
  { label: null, sections: [{ label: "Account", path: "/settings/account" }] },
  {
    label: "Organization",
    sections: [
      { label: "General", path: "/settings/organization" },
      { label: "Members", path: "/settings/organization/members" },
      { label: "Invitations", path: INVITATIONS_PATH },
    ],
  },
  {
    label: null,
    sections: [
      { label: "Secrets", path: "/settings/secrets" },
      { label: "Saved logins", path: "/settings/logins" },
      { label: "Browser extension", path: "/settings/extension" },
    ],
  },
];

/**
 * The sections this role is offered.
 *
 * No role is missing from the answer: a member is shown the Organization's
 * general section and its members, because reading who else is in a team is
 * every role's — only managing who joins it is not.
 *
 * No active Organization means no role to gate by, and the narrowest answer is
 * the honest one.
 */
export function settingsNav(role: Role | null): SettingsGroup[] {
  const manages = role === "owner" || role === "admin";

  return SETTINGS_GROUPS.map((group) => ({
    label: group.label,
    sections: group.sections.filter((section) => manages || section.path !== INVITATIONS_PATH),
  }));
}
