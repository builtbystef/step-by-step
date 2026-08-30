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

export function refusalMessage(error: unknown): string {
  const code =
    typeof error === "object" && error !== null && "code" in error ? error.code : undefined;
  return (typeof code === "string" ? REFUSALS[code] : undefined) ?? UNKNOWN_REFUSAL;
}
