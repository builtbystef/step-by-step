import type { Account, OrganizationMembership } from "@step-by-step/api-client";

const REFUSALS: Record<string, string> = {
  sole_owner:
    "You still own an Organization. Hand it on to somebody else, or delete it, and then this account can go.",
  confirmation_mismatch: "That is not this account's email address.",
};

const UNKNOWN_REFUSAL = "Something went wrong. Try again in a moment.";

export function refusalMessage(error: unknown): string {
  const code =
    typeof error === "object" && error !== null && "code" in error ? error.code : undefined;
  return (typeof code === "string" ? REFUSALS[code] : undefined) ?? UNKNOWN_REFUSAL;
}

export function emailConfirms(typed: string, email: string): boolean {
  return typed.trim().toLowerCase() === email.trim().toLowerCase();
}

export function ownedOrganizations(me: Account | null): OrganizationMembership[] {
  return (me?.orgs ?? []).filter((org) => org.role === "owner");
}

export function soleOwnerExplanation(owned: OrganizationMembership[]): string {
  const names = owned.map((org) => org.name).join(", ");
  return (
    `You are the owner of ${names}. An Organization has exactly one owner, so hand each one ` +
    "on to another member — or delete it — before deleting this account."
  );
}

export function endingConsequence(): string {
  return (
    "Deleting this account ends every session on every browser, leaves every Organization you " +
    "are in, and removes your account for good. This cannot be undone."
  );
}
