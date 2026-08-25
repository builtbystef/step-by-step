import { COPY } from "../../../../lib/copy";

/**
 * What the cockpit says when a call comes back refused.
 */

const REFUSALS: Record<string, string> = {
  run_not_found: "That Run is gone — somebody deleted it, or it was never here.",
  run_terminal: "That Run has already finished.",
  run_active: "A Run that is still going cannot be deleted.",
  missing_secret: "A Secret this Workflow needs is missing.",
  no_published_version: COPY.noPublishedVersion,
  not_a_member: "You are no longer a member of that Organization.",
};

const UNKNOWN_REFUSAL = "Something went wrong. Try again in a moment.";

export function refusalMessage(error: unknown): string {
  const code =
    typeof error === "object" && error !== null && "code" in error ? error.code : undefined;
  return (typeof code === "string" ? REFUSALS[code] : undefined) ?? UNKNOWN_REFUSAL;
}
