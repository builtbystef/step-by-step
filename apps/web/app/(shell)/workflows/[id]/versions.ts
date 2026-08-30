import type { DraftState, VersionSummary } from "@step-by-step/api-client";

import { EDITOR, tabPath } from "./tabs";

const VERSION_PARAM = "version";

export type VersionChoice = {
  label: string;
  version: number | null;
  publishedAt: string | null;
  open: boolean;
};

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

export function versionPath(workflowId: string, version: number | null): string {
  const editor = tabPath(workflowId, EDITOR);
  return version === null ? editor : `${editor}?${VERSION_PARAM}=${String(version)}`;
}

export function viewedVersion(param: string | null | undefined): number | null {
  if (param === null || param === undefined) {
    return null;
  }
  const number = Number(param);
  return Number.isInteger(number) && number >= 1 ? number : null;
}

export function restoreConsequence(version: number, state: DraftState): string {
  const name = `v${String(version)}`;
  const replaced =
    state === "unpublished-changes"
      ? `Restoring ${name} replaces the Draft, including changes no Version carries yet.`
      : `Restoring ${name} replaces the Draft with what ${name} holds.`;
  return `${replaced} Nothing that runs changes until you publish.`;
}
