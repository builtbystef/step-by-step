import type { OfferedMembership, Role } from "@step-by-step/api-client";

const REFUSALS: Record<string, string> = {
  invitation_not_found:
    "That Invitation is no longer standing. It was revoked, taken, or it expired.",
  already_member: "You are already in that Organization.",
};

const UNKNOWN_REFUSAL = "Something went wrong. Try again in a moment.";

export function acceptRefusal(error: unknown): string {
  const code =
    typeof error === "object" && error !== null && "code" in error ? error.code : undefined;
  return (typeof code === "string" ? REFUSALS[code] : undefined) ?? UNKNOWN_REFUSAL;
}

export function offerSentence(offer: OfferedMembership): string {
  return `${offer.org_name} invited you to join as ${article(offer.role)} ${offer.role}.`;
}

function article(role: Role): string {
  return role === "admin" ? "an" : "a";
}
