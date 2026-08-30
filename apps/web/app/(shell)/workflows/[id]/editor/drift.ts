export type RankedResult = {
  step_id: string;
  matched_candidate_rank: number | null;
};

export function isDrifted(rank: number | null): boolean {
  return rank !== null && rank > 0;
}

export function driftedStepIds(results: readonly RankedResult[]): Set<string> {
  return new Set(
    results
      .filter((result) => isDrifted(result.matched_candidate_rank))
      .map((result) => result.step_id),
  );
}

export const DRIFT_WARNING =
  "Recent Runs found this element through a lower-ranked selector. Re-pick or edit the candidates.";

export function repairFromDrift(stepId: string): { expand: string; openSelector: true } {
  return { expand: stepId, openSelector: true };
}
