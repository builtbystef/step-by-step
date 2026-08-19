import type { OfferedMembership, Role } from "@step-by-step/api-client";

/**
 * What the shell says for itself.
 *
 * Only the pending-invitation banner speaks from the chrome today; the rest of
 * the shell's words are the names of its destinations, which the nav owns.
 *
 * A refusal is chosen by its `code` and never by its prose, the way every
 * screen in this app reads the backend.
 */

const REFUSALS: Record<string, string> = {
  invitation_not_found:
    "That Invitation is no longer standing — it was revoked, taken, or it expired.",
  already_member: "You are already in that Organization.",
};

const UNKNOWN_REFUSAL = "Something went wrong. Try again in a moment.";

/** What the banner shows when accepting an Invitation was refused. */
export function acceptRefusal(error: unknown): string {
  const code =
    typeof error === "object" && error !== null && "code" in error ? error.code : undefined;
  return (typeof code === "string" ? REFUSALS[code] : undefined) ?? UNKNOWN_REFUSAL;
}

/** The banner's sentence: who wants this visitor, and as what. */
export function offerSentence(offer: OfferedMembership): string {
  return `${offer.org_name} invited you to join as ${article(offer.role)} ${offer.role}.`;
}

/** "an admin", "a member" — the one place this reads as English. */
function article(role: Role): string {
  return role === "admin" ? "an" : "a";
}
