import type { Target } from "@step-by-step/api-client";

import { targetsOf, type Step } from "./steps";

import type { AttributeTone } from "../../../../../components/primitives/attribute-badge";
import { duration } from "../../../../../lib/duration";

/**
 * The right-hand column of a card: what is true of a Step that its sentence
 * does not say.
 *
 * Every one of them is a property of the Step rather than something it is
 * doing, so every one of them is an `AttributeBadge` — a Step is not in a
 * state until a Run puts it in one.
 *
 * The two that mean attention come from the document the recorder wrote:
 * unsupported is a target it knows will not be findable again, and fragile is
 * a target it could only pin down by where it sat on the page. Neither is
 * computed here; both are read.
 */

export type StepBadge = {
  key: string;
  label: string;
  tone: AttributeTone;
  title?: string;
};

export type TargetHealth =
  | { state: "ok" }
  | { state: "fragile" }
  | { state: "unsupported"; warning: string };

/**
 * How well this Step will find its element again.
 *
 * A Step is only as findable as its least findable target, and unsupported
 * outranks fragile: an element behind a closed shadow root is not a weaker
 * selector, it is no selector at all.
 *
 * "Position-based" is what a CSS candidate is. The seven kinds above it in
 * the ranking were all read from something the page says out loud — a test
 * id, a role and name, a placeholder, a label, alt text, text, a title — and
 * a target that offered none of them is one the page can rearrange out from
 * under.
 */
/** How well one target will find its element again. */
export function healthOf(target: Target): TargetHealth {
  if (target.unsupported) {
    return { state: "unsupported", warning: target.unsupported.warning };
  }
  return target.candidates.every((candidate) => candidate.kind === "css")
    ? { state: "fragile" }
    : { state: "ok" };
}

export function targetHealth(step: Step): TargetHealth {
  const targets = targetsOf(step);
  if (targets.length === 0) {
    return { state: "ok" };
  }
  const healths = targets.map(healthOf);
  const sealed = healths.find((health) => health.state === "unsupported");
  if (sealed?.state === "unsupported") {
    return sealed;
  }
  return healths.some((health) => health.state === "fragile")
    ? { state: "fragile" }
    : { state: "ok" };
}

const FRAGILE_WARNING =
  "Only where this element sat on the page was recorded. A layout change will lose it — " +
  "re-pick it to record a better way of finding it.";

/**
 * What this Step's badge column states, in the order it states it: the
 * envelope first, and the health of the target last, where the eye lands.
 *
 * The screenshot toggle sits in the same column and is not here: it is the
 * one thing in that column a person operates rather than reads, so the card
 * draws it as the control it is.
 */
export function stepBadges(step: Step, workflowDefaultMs: number): StepBadge[] {
  const badges: StepBadge[] = [];
  if (step.optional === true) {
    badges.push({
      key: "optional",
      label: "optional",
      tone: "neutral",
      title: "If the element never appears, the Run skips this Step instead of failing.",
    });
  }
  if (step.disabled === true) {
    badges.push({
      key: "off",
      label: "off",
      tone: "neutral",
      title: "Stays in the Workflow and does not run.",
    });
  }
  if (step.timeoutMs !== undefined && step.timeoutMs !== null) {
    badges.push({
      key: "timeout",
      label: duration(step.timeoutMs),
      tone: "neutral",
      title: `This Step waits ${duration(step.timeoutMs)} rather than the workflow default of ${duration(workflowDefaultMs)}.`,
    });
  }
  const health = targetHealth(step);
  if (health.state === "unsupported") {
    badges.push({
      key: "unsupported",
      label: "unsupported",
      tone: "bad",
      title: health.warning,
    });
  } else if (health.state === "fragile") {
    badges.push({ key: "fragile", label: "fragile", tone: "wait", title: FRAGILE_WARNING });
  }
  return badges;
}
