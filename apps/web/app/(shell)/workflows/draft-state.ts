import type { DraftState } from "@step-by-step/api-client";

import type { AttributeTone } from "../../../components/primitives/attribute-badge";
import { COPY } from "../../../lib/copy";

/**
 * Where a Draft stands, as the list row and the Workflow header both render it.
 *
 * A draft state is a property of a Workflow and never a lifecycle state, so it
 * wears an `AttributeBadge` rather than a `StatusChip` — that is the first of
 * the spec's four arbitrations, and it is what keeps a chip meaning "this is
 * happening".
 */

export type DraftStateBadge = {
  label: string;
  tone: AttributeTone;
};

export function draftStateBadge(
  state: DraftState,
  publishedVersion: number | null | undefined,
): DraftStateBadge {
  if (state === "never-published") {
    return { label: "not published yet", tone: "neutral" };
  }
  if (state === "unpublished-changes") {
    return { label: "unpublished changes", tone: "wait" };
  }
  return { label: `in sync with v${String(publishedVersion ?? "")}`, tone: "ok" };
}

/**
 * Why this Workflow cannot be run, or nothing when it can.
 *
 * One sentence, from `lib/copy.ts`, because the list row, the Workflow header,
 * both creation pages, and a `409 no_published_version` all say it — and a
 * reason phrased four ways is four reasons as far as a reader is concerned.
 */
export function refusalToRun(state: DraftState): string | null {
  return state === "never-published" ? COPY.noPublishedVersion : null;
}
