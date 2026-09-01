import { COPY } from "../../../../lib/copy";

const REFUSALS: Record<string, string> = {
  run_not_found: "That Run is gone. Somebody deleted it, or it was never here.",
  run_terminal: "That Run has already finished.",
  run_active: "A Run that is still going cannot be deleted.",
  missing_secret: "A Secret this Workflow needs is missing.",
  no_published_version: COPY.noPublishedVersion,
  not_a_member: "You are no longer a member of that Organization.",
  already_held: "Control is held in another tab.",
  not_waiting: "This Run is not waiting for a person.",
  not_held: "This tab does not hold control.",
  not_a_candidate: "That domain was not reported as a new login.",
  no_starter: "A Scheduled or Batch Run can only keep a login for the Organization.",
};

const UNKNOWN_REFUSAL = "Something went wrong. Try again in a moment.";

export function refusalMessage(error: unknown): string {
  const code =
    typeof error === "object" && error !== null && "code" in error ? error.code : undefined;
  return (typeof code === "string" ? REFUSALS[code] : undefined) ?? UNKNOWN_REFUSAL;
}
