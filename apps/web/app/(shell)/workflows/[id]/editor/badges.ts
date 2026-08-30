import type { Target } from "@step-by-step/api-client";

import { DRIFT_WARNING } from "./drift";
import { targetsOf, type Step } from "./steps";

import type { AttributeTone } from "../../../../../components/primitives/attribute-badge";
import { duration } from "../../../../../lib/duration";

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

export function healthOf(target: Target): TargetHealth {
  if (target.unsupported) {
    return { state: "unsupported", warning: target.unsupported.warning };
  }
  return target.candidates.length === 0 ||
    target.candidates.every((candidate) => candidate.kind === "css")
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

export const EMPTY_WARNING = "no selectors — pick an element";

export function stepBadges(step: Step, workflowDefaultMs: number, drifted = false): StepBadge[] {
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
    const empty = targetsOf(step).some((target) => target.candidates.length === 0);
    badges.push(
      empty
        ? { key: "fragile", label: "no selectors", tone: "wait", title: EMPTY_WARNING }
        : { key: "fragile", label: "fragile", tone: "wait", title: FRAGILE_WARNING },
    );
  }
  if (drifted) {
    badges.push({
      key: "drift",
      label: "drifting",
      tone: "wait",
      title: DRIFT_WARNING,
    });
  }
  return badges;
}
