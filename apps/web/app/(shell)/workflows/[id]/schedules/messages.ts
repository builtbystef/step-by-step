import { COPY } from "../../../../../lib/copy";

const REFUSALS: Record<string, string> = {
  no_published_version: COPY.noPublishedVersion,
  invalid_cron: "That is not a cron expression.",
  invalid_timezone: "That is not an IANA timezone.",
  missing_variable_values: "Every non-secret Variable needs a value.",
  workflow_not_found: "That Workflow is gone. Somebody deleted it, or it was never here.",
  schedule_not_found: "That Schedule is gone. Somebody deleted it, or it was never here.",
  not_a_member: "You are no longer a member of that Organization.",
};

const UNKNOWN_REFUSAL = "Something went wrong. Try again in a moment.";

export function refusalMessage(error: unknown): string {
  const code =
    typeof error === "object" && error !== null && "code" in error ? error.code : undefined;
  return (typeof code === "string" ? REFUSALS[code] : undefined) ?? UNKNOWN_REFUSAL;
}

export function emptyValueMessage(names: readonly string[]): string {
  if (names.length === 0) {
    return "";
  }
  if (names.length === 1) {
    return `${names[0]} has no value. A Schedule cannot be saved without it.`;
  }
  return `${names.join(", ")} have no values. A Schedule cannot be saved without them.`;
}
