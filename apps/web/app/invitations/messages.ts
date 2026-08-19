import type {
  Account,
  OfferedMembership,
  OrganizationMembership,
  Role,
} from "@step-by-step/api-client";

/**
 * What the Invitations screen says, and which Organizations it may manage —
 * decided here rather than in the JSX, so that both are read back directly.
 *
 * A refusal is chosen by its `code` and never by its prose, the way every
 * screen in this app reads the backend.
 */

const REFUSALS: Record<string, string> = {
  already_member: "That address is already in this Organization.",
  already_invited:
    "That address already has an Invitation standing. Revoke it before inviting them again.",
  not_an_admin: "Only an owner or an admin can manage Invitations.",
  not_a_member: "You are no longer a member of that Organization.",
  invitation_not_found:
    "That Invitation is no longer standing — it was revoked, taken, or it expired.",
};

const UNKNOWN_REFUSAL = "Something went wrong. Try again in a moment.";

/** What the screen shows for a refusal, or for anything else that came back. */
export function refusalMessage(error: unknown): string {
  const code =
    typeof error === "object" && error !== null && "code" in error ? error.code : undefined;
  return (typeof code === "string" ? REFUSALS[code] : undefined) ?? UNKNOWN_REFUSAL;
}

/**
 * The Organizations whose Invitations this account may manage.
 *
 * The same rule the backend enforces, said again here for one reason: a panel
 * of controls that would every one of them answer 403 is worse than no panel.
 * It is not the guard — the guard is the backend's.
 */
export function manageableOrgs(me: Account | null): OrganizationMembership[] {
  return (me?.orgs ?? []).filter((org) => org.role !== "member");
}

/** The banner's sentence: who wants this visitor, and as what. */
export function offerSentence(offer: OfferedMembership): string {
  return `${offer.org_name} invited you to join as ${article(offer.role)} ${offer.role}.`;
}

/** "an admin", "a member" — the one place this reads as English. */
function article(role: Role): string {
  return role === "admin" ? "an" : "a";
}
