import { COPY } from "../../../../../../lib/copy";

/**
 * What the Batch creation page says when create or copy comes back refused.
 */

const REFUSALS: Record<string, string> = {
  no_published_version: COPY.noPublishedVersion,
  unknown_variable: "A row names a Variable this Workflow does not declare.",
  too_many_rows: "A Batch can hold at most 1 000 rows.",
  workflow_not_found: "That Workflow is gone — somebody deleted it, or it was never here.",
  batch_not_found: "That Batch is gone — somebody deleted it, or it was never here.",
  not_a_member: "You are no longer a member of that Organization.",
};

const UNKNOWN_REFUSAL = "Something went wrong. Try again in a moment.";

export function refusalMessage(error: unknown): string {
  const code =
    typeof error === "object" && error !== null && "code" in error ? error.code : undefined;
  return (typeof code === "string" ? REFUSALS[code] : undefined) ?? UNKNOWN_REFUSAL;
}
