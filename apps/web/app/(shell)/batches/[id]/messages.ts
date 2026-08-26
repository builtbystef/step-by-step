/**
 * What the batch view says when a call comes back refused.
 */

const REFUSALS: Record<string, string> = {
  batch_not_found: "That Batch is gone — somebody deleted it, or it was never here.",
  not_a_member: "You are no longer a member of that Organization.",
  not_waiting: "This row is not waiting for a person.",
  run_terminal: "That Run has already finished.",
  already_held: "Control is held in another tab.",
};

const UNKNOWN_REFUSAL = "Something went wrong. Try again in a moment.";

export function refusalMessage(error: unknown): string {
  const code =
    typeof error === "object" && error !== null && "code" in error ? error.code : undefined;
  return (typeof code === "string" ? REFUSALS[code] : undefined) ?? UNKNOWN_REFUSAL;
}
