import type { Member, Role } from "@step-by-step/api-client";

const REFUSALS: Record<string, string> = {
  not_a_member: "You are no longer a member of that Organization.",
  not_an_admin: "Only an owner or an admin can do that.",
  not_the_owner: "Only the owner can hand the Organization on.",
  is_owner: "The owner's place cannot be changed or ended — hand it on first.",
  member_not_found: "That person is no longer in this Organization.",
  confirmation_mismatch: "That is not this Organization's name.",
};

const UNKNOWN_REFUSAL = "Something went wrong. Try again in a moment.";

export function refusalMessage(error: unknown): string {
  const code =
    typeof error === "object" && error !== null && "code" in error ? error.code : undefined;
  return (typeof code === "string" ? REFUSALS[code] : undefined) ?? UNKNOWN_REFUSAL;
}

export function mayRename(viewerRole: Role): boolean {
  return viewerRole !== "member";
}

export function mayEnd(viewerRole: Role): boolean {
  return viewerRole === "owner";
}

export function nameConfirms(typed: string, name: string): boolean {
  return typed.trim() === name.trim();
}

export function endingConsequence(orgName: string): string {
  return (
    `Everything in ${orgName} goes with it: every Workflow and Run, every pending Invitation, ` +
    "and everybody's Membership. The people keep their accounts and their other Organizations. " +
    "This cannot be undone."
  );
}

export type MemberControls = {
  changeRole: boolean;
  remove: boolean;
  leave: boolean;
  makeOwner: boolean;
};

const NOTHING: MemberControls = {
  changeRole: false,
  remove: false,
  leave: false,
  makeOwner: false,
};

export function memberControls(
  viewer: { role: Role; userId: string },
  row: Member,
): MemberControls {
  if (row.role === "owner") {
    return NOTHING;
  }
  if (row.user_id === viewer.userId) {
    return { ...NOTHING, leave: viewer.role !== "owner" };
  }
  if (viewer.role === "member") {
    return NOTHING;
  }
  return {
    changeRole: true,
    remove: true,
    leave: false,
    makeOwner: viewer.role === "owner",
  };
}

export function memberLabel(row: Member): string {
  return row.display_name ? `${row.display_name} (${row.email})` : row.email;
}

export function transferConsequence(row: Member, orgName: string): string {
  return (
    `${memberLabel(row)} becomes the owner of ${orgName}, and you become an admin. ` +
    "Only the new owner can hand it back."
  );
}
