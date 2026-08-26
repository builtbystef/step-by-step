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
  run_active:
    "A Run of this Workflow is still going. Wait for it to finish, or cancel it, then try again.",
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
 * The confirm names the Schedules and Runs that go with the Workflow, so the
 * blast radius is a fact rather than a guess. Zero of either is omitted: a
 * count of nothing is noise.
 */
export function deletionConsequence(workflow: {
  draft_state: DraftState;
  published_version?: number | null;
  schedule_count?: number;
  run_count?: number;
}): string {
  const versions = workflow.published_version ?? 0;
  const alsoVersions =
    versions > 0
      ? ` and its ${String(versions)} published Version${versions === 1 ? "" : "s"}`
      : "";
  const cascade = namedCounts([
    [workflow.schedule_count ?? 0, "Schedule"],
    [workflow.run_count ?? 0, "Run"],
  ]);
  const alsoCascade = cascade === null ? "" : ` ${cascade} will be deleted.`;
  return `Its Draft${alsoVersions} will be deleted.${alsoCascade} This cannot be undone.`;
}

function namedCounts(items: [number, string][]): string | null {
  const named = items
    .filter(([count]) => count > 0)
    .map(([count, noun]) => `${String(count)} ${noun}${count === 1 ? "" : "s"}`);
  if (named.length === 0) {
    return null;
  }
  return named.join(" and ");
}

/**
 * What the list row says about Schedules: the one Schedule's label, or a
 * count, or nothing when the Workflow has none.
 */
export function scheduleIndicator(workflow: {
  schedule_count: number;
  schedule_label?: string | null;
}): string | null {
  if (workflow.schedule_count === 0) {
    return null;
  }
  if (workflow.schedule_count === 1) {
    return workflow.schedule_label ?? "1 schedule";
  }
  return `${String(workflow.schedule_count)} schedules`;
}
