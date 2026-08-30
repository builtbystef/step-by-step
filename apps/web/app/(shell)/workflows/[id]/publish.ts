import type { DraftComparison, StepRef, StrandedScheduleRef } from "@step-by-step/api-client";

import { humanize } from "../../../../lib/recurrence";

export type DiffSection = {
  key: "added" | "changed" | "removed";
  heading: string;
  steps: StepRef[];
};

export type PublishPlan = {
  number: number;
  sections: DiffSection[];
  note: string | null;
  worthPublishing: boolean;
  warning: string | null;
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
    warning: strandedWarning(comparison.stranded_schedules),
  };
}

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

function strandedWarning(schedules: readonly StrandedScheduleRef[]): string | null {
  if (schedules.length === 0) {
    return null;
  }
  const named = schedules.map(scheduleLabel);
  const whose = schedules.length === 1 ? "its" : "their";
  return `${joinNames(named)} will stop firing until ${whose} values are set.`;
}

function scheduleLabel(schedule: StrandedScheduleRef): string {
  if (schedule.name !== null && schedule.name !== "") {
    return schedule.name;
  }
  return humanize(schedule.cron) ?? schedule.cron;
}

function joinNames(names: readonly string[]): string {
  if (names.length === 1) {
    return names[0] ?? "";
  }
  if (names.length === 2) {
    return `${names[0]} and ${names[1]}`;
  }
  return `${names.slice(0, -1).join(", ")}, and ${names[names.length - 1]}`;
}
