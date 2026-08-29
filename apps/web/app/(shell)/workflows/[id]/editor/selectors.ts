import type { CandidateKind, SelectorCandidate, Target } from "@step-by-step/api-client";

import type { TargetHealth } from "./badges";

import type { AttributeTone } from "../../../../../components/primitives/attribute-badge";

/**
 * The selector panel's decisions: the health badge's words, what the
 * candidate tools do to the list, and whether Re-pick may start.
 *
 * Candidates are plain stored data. Hand-edits rewrite the list and save
 * through the Draft API like any other edit. Re-pick is the other repair
 * path, and it is refused while this editor holds unsaved work — finalize
 * patches the server Draft, and a dirty local copy would race it.
 */

/** The kinds, in the order the recorder ranks them. */
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

/**
 * The collapsed badge, in the spec's words.
 *
 * Green counts the verified ways; amber is a target only position can find;
 * red is the recorder's own warning, verbatim. Zero candidates is not a
 * healthy zero — it is an element nobody has pointed at yet.
 */
export function selectorHealthCopy(health: TargetHealth, count: number): string {
  if (health.state === "unsupported") {
    return health.warning;
  }
  if (count === 0) {
    return "no selectors — pick an element";
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

/**
 * A CSS candidate is the one kind that was read from where the element sat,
 * not from something the page said out loud — the same fact the fragile
 * badge names, told apart here by the chip's hue.
 */
export function candidateKindTone(kind: CandidateKind): AttributeTone {
  return kind === "css" ? "wait" : "accent";
}

/**
 * Every persisted candidate was unique at capture. Hand-edits do not store a
 * second opinion, so the column says what the recorder guaranteed.
 */
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

/** The same target, with a different candidate list and nothing else changed. */
export function withCandidates(target: Target, candidates: SelectorCandidate[]): Target {
  return { ...target, candidates };
}

/**
 * Re-pick finalize patches the server Draft. Starting one while this tab
 * holds unsaved edits would let that write race the local copy.
 */
export function repickRefusal(unsaved: boolean): string | null {
  return unsaved ? "Save or discard your editor changes before re-picking." : null;
}
