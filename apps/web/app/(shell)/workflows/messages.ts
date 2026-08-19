import type { DraftState } from "@step-by-step/api-client";

import { COPY } from "../../../lib/copy";

/**
 * What the Workflows screens say: the refusals, and the consequence a delete
 * asks to be agreed to.
 *
 * A refusal is chosen by its `code` and never by its prose, the way every
 * screen in this app reads the backend. One of them is not this module's to
 * word: a Workflow with no published Version is refused in the sentence
 * `lib/copy.ts` holds, because four surfaces say it and they must say it
 * identically.
 */

const REFUSALS: Record<string, string> = {
  workflow_not_found: "That Workflow is gone — somebody deleted it, or it was never here.",
  no_published_version: COPY.noPublishedVersion,
  bad_cursor: "That page is no longer where it was. Reload the list.",
  not_a_member: "You are no longer a member of that Organization.",
};

const UNKNOWN_REFUSAL = "Something went wrong. Try again in a moment.";

/** What a screen shows for a refusal, or for anything else that came back. */
export function refusalMessage(error: unknown): string {
  const code =
    typeof error === "object" && error !== null && "code" in error ? error.code : undefined;
  return (typeof code === "string" ? REFUSALS[code] : undefined) ?? UNKNOWN_REFUSAL;
}

/**
 * What goes with a Workflow, named before the delete is agreed to.
 *
 * A plain confirm names its blast radius and asks once. Typing the name back
 * is reserved for ending an account (`ufnuvx`), and spending that ceremony on
 * routine housekeeping would spend it everywhere.
 *
 * The Schedules, Batches, and Runs it will also name arrive with the slice
 * that gives a Workflow any: naming a count of nothing would be noise.
 */
export function deletionConsequence(workflow: {
  draft_state: DraftState;
  published_version?: number | null;
}): string {
  const versions = workflow.published_version ?? 0;
  const alsoVersions =
    versions > 0
      ? ` and its ${String(versions)} published Version${versions === 1 ? "" : "s"}`
      : "";
  return `Its Draft${alsoVersions} will be deleted. This cannot be undone.`;
}
