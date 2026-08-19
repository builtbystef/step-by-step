import type { Member, Role } from "@step-by-step/api-client";

/**
 * What the Organization screen says, and which control each row offers —
 * decided here rather than in the JSX, so that the whole permission table is
 * read back directly.
 *
 * The rules are the backend's, said again for one reason: a row of controls
 * that would every one of them answer 403 is worse than a row without them.
 * They are not the guard — the guard is the backend's.
 */

const REFUSALS: Record<string, string> = {
  not_a_member: "You are no longer a member of that Organization.",
  not_an_admin: "Only an owner or an admin can do that.",
  not_the_owner: "Only the owner can hand the Organization on.",
  is_owner: "The owner's place cannot be changed or ended — hand it on first.",
  member_not_found: "That person is no longer in this Organization.",
};

const UNKNOWN_REFUSAL = "Something went wrong. Try again in a moment.";

/** What the screen shows for a refusal, or for anything else that came back. */
export function refusalMessage(error: unknown): string {
  const code =
    typeof error === "object" && error !== null && "code" in error ? error.code : undefined;
  return (typeof code === "string" ? REFUSALS[code] : undefined) ?? UNKNOWN_REFUSAL;
}

/** Renaming an Organization is the owner's and the admins', never a member's. */
export function mayRename(viewerRole: Role): boolean {
  return viewerRole !== "member";
}

/** The controls one row offers the person reading it. */
export type MemberControls = {
  /** Move them between member and admin. */
  changeRole: boolean;
  /** End their Membership. */
  remove: boolean;
  /** End your own, which is the same act asked by the person it is about. */
  leave: boolean;
  /** Hand them the Organization, which makes you an admin. */
  makeOwner: boolean;
};

const NOTHING: MemberControls = {
  changeRole: false,
  remove: false,
  leave: false,
  makeOwner: false,
};

/**
 * Who may do what to one Membership — the backend's table, in one place:
 *
 * | the row is the owner's | nothing: it changes only by transfer   |
 * | the row is your own    | leave, unless you are the owner        |
 * | you are a member       | nothing: members manage nobody         |
 * | otherwise              | role and removal; transfer if you own  |
 */
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

/** How a row names a person: the name they gave, and always the address. */
export function memberLabel(row: Member): string {
  return row.display_name ? `${row.display_name} (${row.email})` : row.email;
}

/**
 * What handing the Organization on will do, said before it is done.
 *
 * Both halves, because the second is the one nobody expects: the person who
 * asks for this is the person who stops being the owner.
 */
export function transferConsequence(row: Member, orgName: string): string {
  return (
    `${memberLabel(row)} becomes the owner of ${orgName}, and you become an admin. ` +
    "Only the new owner can hand it back."
  );
}
