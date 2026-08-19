import type { DraftComparison, StepRef } from "@step-by-step/api-client";

/**
 * What publishing would do, as the modal in front of it states.
 *
 * The Draft and the latest Version are compared by the backend, in the one
 * derivation the Draft chip also reads, so nothing is computed here — this is
 * that answer arranged into the thing a person confirms against: the number
 * about to be minted, the Steps that change, and a sentence for the cases
 * where a step-level diff has nothing to show and is not thereby empty.
 */

export type DiffSection = {
  key: "added" | "changed" | "removed";
  heading: string;
  steps: StepRef[];
};

export type PublishPlan = {
  /** The Version confirming would mint. */
  number: number;
  /** The three lists, with the ones nothing is in left out. */
  sections: DiffSection[];
  /** What no section says, or nothing when the sections say it all. */
  note: string | null;
  /** Whether confirming would leave the Workflow any different. */
  worthPublishing: boolean;
};

export function publishPlan(comparison: DraftComparison): PublishPlan {
  const sections: DiffSection[] = (
    [
      { key: "added", heading: "Added", steps: comparison.added },
      { key: "changed", heading: "Changed", steps: comparison.changed },
      { key: "removed", heading: "Removed", steps: comparison.removed },
    ] as const
  )
    .filter((section) => section.steps.length > 0)
    .map((section) => ({ ...section, steps: [...section.steps] }));

  return {
    number: (comparison.latest_version ?? 0) + 1,
    sections,
    note: note(comparison, sections),
    worthPublishing: comparison.state !== "in-sync",
  };
}

/**
 * The three ways a diff of no Steps still means something.
 *
 * A Draft in sync has nothing to publish at all. A Draft that differs while
 * every list is empty moved something a step diff cannot show — the order, or
 * the Variables, both of which travel in the same document. And before a
 * first publish, an empty diff is an empty Workflow, because everything a
 * first publish carries is listed as added.
 */
function note(comparison: DraftComparison, sections: DiffSection[]): string | null {
  if (comparison.state === "in-sync") {
    return `Nothing has changed since v${String(comparison.latest_version)}. Publishing again would mint a Version identical to it.`;
  }
  if (sections.length > 0) {
    return null;
  }
  if (comparison.latest_version === null) {
    return "This Workflow has no Steps yet. Publishing mints a Version that does nothing.";
  }
  return "No Step was added, removed, or changed. What moved is the order of the Steps, or the Variables they stand on.";
}
