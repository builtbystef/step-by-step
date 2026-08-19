import type { DraftState, VersionSummary } from "@step-by-step/api-client";

import { EDITOR, tabPath } from "./tabs";

/**
 * The version surface of a Workflow: what the header's dropdown offers, which
 * of its entries an address is showing, and what restoring one costs.
 *
 * Which Version is open is the address's, not a component's, for the reason
 * the tabs are segments: a Version somebody is reading is a place, so it
 * survives a reload and can be sent to somebody else. It is a query rather
 * than a fifth segment because it is the same editor either way — the Draft
 * and its Versions are one screen, showing one document or another.
 */

/** The query the editor's address carries when it is showing a past Version. */
const VERSION_PARAM = "version";

export type VersionChoice = {
  /** What the dropdown writes: "Draft", or "v3". */
  label: string;
  /** The Version this opens, and null for the Draft. */
  version: number | null;
  /** When it was published, and null for the Draft, which never was. */
  publishedAt: string | null;
  /** Whether this is the one on screen. */
  open: boolean;
};

/**
 * Everything this Workflow can be shown as: the Draft, then every Version.
 *
 * Newest first under the Draft, because a dropdown is read from the top and
 * the Version somebody wants is nearly always the last one — v1 of a Workflow
 * published forty times is the entry furthest from the hand.
 */
export function versionChoices(
  versions: readonly VersionSummary[],
  viewing: number | null,
): VersionChoice[] {
  const past = [...versions]
    .sort((one, other) => other.number - one.number)
    .map((version) => ({
      label: `v${String(version.number)}`,
      version: version.number,
      publishedAt: version.created_at,
      open: version.number === viewing,
    }));
  return [{ label: "Draft", version: null, publishedAt: null, open: viewing === null }, ...past];
}

/** Where the editor shows the Draft, or one past Version. */
export function versionPath(workflowId: string, version: number | null): string {
  const editor = tabPath(workflowId, EDITOR);
  return version === null ? editor : `${editor}?${VERSION_PARAM}=${String(version)}`;
}

/**
 * The Version an address is showing, or nothing when it is showing the Draft.
 *
 * Anything that is not a Version number reads as the Draft rather than as an
 * error: a query somebody trimmed by hand should land on the editor, not on a
 * screen about a malformed address.
 */
export function viewedVersion(param: string | null | undefined): number | null {
  if (param === null || param === undefined) {
    return null;
  }
  const number = Number(param);
  return Number.isInteger(number) && number >= 1 ? number : null;
}

/**
 * What restoring a Version does, said before it is done.
 *
 * Restore overwrites the Draft, so the sentence names what is overwritten —
 * and a Draft holding changes no Version carries is the case where that is
 * somebody's unpublished work rather than a copy of something published.
 *
 * Both readings end the same way, because both are asked in front of a
 * Workflow that Schedules and Batches may be running: restoring is an edit of
 * the Draft, and what runs does not move until a publish.
 */
export function restoreConsequence(version: number, state: DraftState): string {
  const name = `v${String(version)}`;
  const replaced =
    state === "unpublished-changes"
      ? `Restoring ${name} replaces the Draft, including changes no Version carries yet.`
      : `Restoring ${name} replaces the Draft with what ${name} holds.`;
  return `${replaced} Nothing that runs changes until you publish.`;
}
