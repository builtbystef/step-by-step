const REFUSALS: Record<string, string> = {
  duplicate_step_id: "Two Steps carry the same id, so the Draft was not saved.",
  undeclared_variable:
    "A value uses a Variable this Workflow does not declare, so the Draft was not saved.",
  duplicate_variable_name: "Two Variables carry the same name, so the Draft was not saved.",
  unknown_step_type:
    "A Step here is of a type this instance cannot run, so the Draft was not saved.",
  malformed_payload:
    "A Step here is not filled in the way its type needs, so the Draft was not saved.",
  workflow_not_found: "That Workflow is gone. Somebody deleted it, or it was never here.",
};

const UNKNOWN_REFUSAL = "The Draft was not saved. Try again in a moment.";

export function saveRefusal(error: unknown): string {
  const said = error as { code?: unknown; message?: unknown } | null | undefined;
  const sentence =
    typeof said?.code === "string" ? (REFUSALS[said.code] ?? UNKNOWN_REFUSAL) : UNKNOWN_REFUSAL;
  const detail =
    sentence === UNKNOWN_REFUSAL || typeof said?.message !== "string" ? "" : said.message;
  return detail === "" ? sentence : `${sentence}: ${detail}`;
}

const READ_REFUSALS: Record<string, string> = {
  version_not_found: "That Version is not here. The version dropdown lists the ones that are.",
  workflow_not_found: "That Workflow is gone. Somebody deleted it, or it was never here.",
};

const UNKNOWN_READ_REFUSAL = "This document could not be loaded. Try again in a moment.";

export function readRefusal(error: unknown): string {
  const said = error as { code?: unknown } | null | undefined;
  return typeof said?.code === "string"
    ? (READ_REFUSALS[said.code] ?? UNKNOWN_READ_REFUSAL)
    : UNKNOWN_READ_REFUSAL;
}
