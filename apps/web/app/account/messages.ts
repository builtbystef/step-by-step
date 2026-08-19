import type { Account, OrganizationMembership } from "@step-by-step/api-client";

/**
 * What the account screen says, and when its one irreversible control means
 * it — decided here rather than in the JSX, so that both are read back
 * directly.
 *
 * A refusal is chosen by its `code` and never by its prose, the way every
 * screen in this app reads the backend.
 */

const REFUSALS: Record<string, string> = {
  sole_owner:
    "You still own an Organization. Hand it on to somebody else, or delete it, and then this account can go.",
  confirmation_mismatch: "That is not this account's email address.",
};

const UNKNOWN_REFUSAL = "Something went wrong. Try again in a moment.";

/** What the screen shows for a refusal, or for anything else that came back. */
export function refusalMessage(error: unknown): string {
  const code =
    typeof error === "object" && error !== null && "code" in error ? error.code : undefined;
  return (typeof code === "string" ? REFUSALS[code] : undefined) ?? UNKNOWN_REFUSAL;
}

/**
 * Whether what was typed is this account's address.
 *
 * Without case and without surrounding space, because the backend compares it
 * that way: the identity is the mailbox, and a confirmation that refused what
 * the route would accept would be the screen inventing a rule of its own.
 */
export function emailConfirms(typed: string, email: string): boolean {
  return typed.trim().toLowerCase() === email.trim().toLowerCase();
}

/**
 * The Organizations this account owns — the ones that stand in the way.
 *
 * The same rule the backend enforces, said again here for one reason: an
 * account that cannot be deleted yet should learn it from the screen rather
 * than from a 403 after typing its own address out. It is not the guard —
 * the guard is the backend's.
 */
export function ownedOrganizations(me: Account | null): OrganizationMembership[] {
  return (me?.orgs ?? []).filter((org) => org.role === "owner");
}

/** Which teams are still this account's, and the two things to do about them. */
export function soleOwnerExplanation(owned: OrganizationMembership[]): string {
  const names = owned.map((org) => org.name).join(", ");
  return (
    `You are the owner of ${names}. An Organization has exactly one owner, so hand each one ` +
    "on to another member — or delete it — before deleting this account."
  );
}

/** What deleting the account takes with it, said before it is done. */
export function endingConsequence(): string {
  return (
    "Deleting this account ends every session on every browser, leaves every Organization you " +
    "are in, and removes your account for good. This cannot be undone."
  );
}
