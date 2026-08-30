import type { DraftState } from "@step-by-step/api-client";

import type { AttributeTone } from "../../../components/primitives/attribute-badge";
import { COPY } from "../../../lib/copy";

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

export function refusalToRun(state: DraftState): string | null {
  return state === "never-published" ? COPY.noPublishedVersion : null;
}
