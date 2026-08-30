import type { CandidateKind, SelectorCandidate, Target } from "@step-by-step/api-client";

import { EMPTY_WARNING, type TargetHealth } from "./badges";

import type { AttributeTone } from "../../../../../components/primitives/attribute-badge";

export const CANDIDATE_KINDS: readonly CandidateKind[] = [
  "testid",
  "role",
  "placeholder",
  "label",
  "alt",
  "text",
  "title",
  "css",
];

export function selectorHealthCopy(health: TargetHealth, count: number): string {
  if (health.state === "unsupported") {
    return health.warning;
  }
  if (count === 0) {
    return EMPTY_WARNING;
  }
  if (health.state === "fragile") {
    return "fragile — only position-based selectors";
  }
  const noun = count === 1 ? "way" : "ways";
  return `${String(count)} ${noun} to find it — verified when recorded`;
}

export function selectorHealthTone(health: TargetHealth, count: number): AttributeTone {
  if (health.state === "unsupported") {
    return "bad";
  }
  if (health.state === "fragile" || count === 0) {
    return "wait";
  }
  return "ok";
}

export function candidateKindTone(kind: CandidateKind): AttributeTone {
  return kind === "css" ? "wait" : "accent";
}

export function candidateUniqueness(_candidate: SelectorCandidate): {
  label: "unique";
  title: string;
} {
  return { label: "unique", title: "Matched exactly one element at record time" };
}

export function withCandidateMovedToTop(
  candidates: SelectorCandidate[],
  index: number,
): SelectorCandidate[] {
  const moving = candidates[index];
  if (moving === undefined || index === 0) {
    return candidates;
  }
  return [moving, ...candidates.filter((_, at) => at !== index)];
}

export function withCandidateRemoved(
  candidates: SelectorCandidate[],
  index: number,
): SelectorCandidate[] {
  if (candidates[index] === undefined) {
    return candidates;
  }
  return candidates.filter((_, at) => at !== index);
}

export function withCandidateAdded(
  candidates: SelectorCandidate[],
  candidate: SelectorCandidate,
): SelectorCandidate[] {
  return [...candidates, candidate];
}

export function withCandidates(target: Target, candidates: SelectorCandidate[]): Target {
  return { ...target, candidates };
}

export function repickRefusal(unsaved: boolean): string | null {
  return unsaved ? "Save or discard your editor changes before re-picking." : null;
}
