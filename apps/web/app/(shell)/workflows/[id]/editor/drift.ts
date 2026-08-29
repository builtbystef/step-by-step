/**
 * Selector Drift as the editor shows it: an aggregate over recent Step
 * Results, on the card of the Step that drifted, because that is where
 * repair happens.
 *
 * Rank is 0-indexed. 0 is the recorded best candidate; anything above it
 * means the page has moved under the Workflow.
 */

export type RankedResult = {
  step_id: string;
  matched_candidate_rank: number | null;
};

export function isDrifted(rank: number | null): boolean {
  return rank !== null && rank > 0;
}

/** The Step ids that resolved through a lower-ranked candidate in this window. */
export function driftedStepIds(results: readonly RankedResult[]): Set<string> {
  return new Set(
    results
      .filter((result) => isDrifted(result.matched_candidate_rank))
      .map((result) => result.step_id),
  );
}

export const DRIFT_WARNING =
  "Recent Runs found this element through a lower-ranked selector. Re-pick or edit the candidates.";

/** Clicking the badge expands this Step and opens its selector panel. */
export function repairFromDrift(stepId: string): { expand: string; openSelector: true } {
  return { expand: stepId, openSelector: true };
}
