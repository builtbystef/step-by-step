import type { Role } from "@step-by-step/api-client";

export type SettingsSection = {
  label: string;
  path: string;
};

export type SettingsGroup = {
  label: string | null;
  sections: SettingsSection[];
};

const INVITATIONS_PATH = "/settings/organization/invitations";

export const SETTINGS_GROUPS: readonly SettingsGroup[] = [
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
      { label: "Invitations", path: INVITATIONS_PATH },
    ],
  },
  {
    label: "Vault",
    sections: [
      { label: "Secrets", path: "/settings/secrets" },
      { label: "Saved logins", path: "/settings/logins" },
    ],
  },
];

export function settingsNav(role: Role | null): SettingsGroup[] {
  const manages = role === "owner" || role === "admin";

  return SETTINGS_GROUPS.map((group) => ({
    label: group.label,
    sections: group.sections.filter((section) => manages || section.path !== INVITATIONS_PATH),
  }));
}
