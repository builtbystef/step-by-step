/**
 * What the editor says when a save comes back refused.
 *
 * The sentence is chosen by the refusal's `code`, the way every screen in
 * this app reads the backend. What is different here is that the backend's
 * own message is kept: the document store validates the document as a whole,
 * so its refusals are about one Step among a hundred, and the id or the
 * Variable name it names is the only thing that says which one. Dropping it
 * would leave a person searching a card list by hand.
 */

const REFUSALS: Record<string, string> = {
  duplicate_step_id: "Two Steps carry the same id, so the Draft was not saved.",
  undeclared_variable:
    "A value uses a Variable this Workflow does not declare, so the Draft was not saved.",
  duplicate_variable_name: "Two Variables carry the same name, so the Draft was not saved.",
  unknown_step_type:
    "A Step here is of a type this instance cannot run, so the Draft was not saved.",
  malformed_payload:
    "A Step here is not filled in the way its type needs, so the Draft was not saved.",
  workflow_not_found: "That Workflow is gone — somebody deleted it, or it was never here.",
};

const UNKNOWN_REFUSAL = "The Draft was not saved. Try again in a moment.";

export function saveRefusal(error: unknown): string {
  const said = error as { code?: unknown; message?: unknown } | null | undefined;
  const sentence =
    typeof said?.code === "string" ? (REFUSALS[said.code] ?? UNKNOWN_REFUSAL) : UNKNOWN_REFUSAL;
  const detail =
    sentence === UNKNOWN_REFUSAL || typeof said?.message !== "string" ? "" : said.message;
  return detail === "" ? sentence : `${sentence} — ${detail}`;
}
