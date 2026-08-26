import type {
  OccurrenceHistoryEntry,
  OccurrenceRecord,
  RunHistoryEntry,
  RunStatus,
} from "@step-by-step/api-client";

import { humanize } from "../../../lib/recurrence";

import { editSchedulePath } from "../workflows/[id]/tabs";

/**
 * The Schedules table's decisions: the row, the strip, the three hole
 * stories, the banners, the enabled patch, and the next-Occurrence labels.
 *
 * The page draws these. It does not re-decide them. Occurrence *times* come
 * from GET /api/schedules/{id}; this module only phrases the timestamps it is
 * given. Recurrence words come from `humanize`.
 */

export function recurrenceHeadline(cron: string): string {
  return humanize(cron) ?? cron;
}

export function recurrenceSubline(
  cron: string,
  timezone: string,
): { cron: string; timezone: string } {
  return { cron, timezone };
}

export function noteOf(
  latest: OccurrenceRecord | null,
  variableNames: readonly string[] = [],
): string {
  if (latest === null) {
    return "";
  }
  return holeStory(latest.reason, variableNames);
}

export type OccurrenceReason = "overlap" | "missed" | "missing_values";

export function holeStory(reason: OccurrenceReason, variableNames: readonly string[] = []): string {
  switch (reason) {
    case "overlap":
      return "The previous Run was still running.";
    case "missed":
      return "The instance was not running. Missed Occurrences are never run late.";
    case "missing_values": {
      const named = variableNames[0];
      if (named !== undefined && variableNames.length === 1) {
        return `This Workflow now needs ${named}, and this Schedule has no value for it.`;
      }
      if (variableNames.length > 1) {
        return `This Workflow now needs ${variableNames.join(", ")}, and this Schedule has no value for them.`;
      }
      return "This Workflow now needs a Variable this Schedule has no value for.";
    }
  }
}

/** The hatch HatchedOccurrence draws for a hole. Three reasons, three hatches. */
export type HoleHatch = "prevented" | "missed" | "missing-values";

export function hatchOf(reason: OccurrenceReason): HoleHatch {
  switch (reason) {
    case "overlap":
      return "prevented";
    case "missed":
      return "missed";
    case "missing_values":
      return "missing-values";
  }
}

export type StripMark =
  | { kind: "run"; at: string; runId: string; status: RunStatus }
  | { kind: OccurrenceReason; at: string; blockingRunId: string | null }
  | { kind: "due"; at: string }
  | { kind: "paused" };

export function stripMarks(input: {
  history: readonly (RunHistoryEntry | OccurrenceHistoryEntry)[];
  nextOccurrences: readonly string[];
  paused: boolean;
}): StripMark[] {
  const past = input.history.map(toStripMark);
  if (input.paused) {
    return [...past, { kind: "paused" }];
  }
  return [...past, ...input.nextOccurrences.map((at) => ({ kind: "due" as const, at }))];
}

function toStripMark(entry: RunHistoryEntry | OccurrenceHistoryEntry): StripMark {
  if (isRunEntry(entry)) {
    return { kind: "run", at: entry.at, runId: entry.run_id, status: entry.status };
  }
  return {
    kind: entry.reason,
    at: entry.at,
    blockingRunId: entry.blocking_run_id ?? null,
  };
}

export type HistoryItem =
  | { kind: "run"; at: string; runId: string; status: RunStatus }
  | {
      kind: "occurrence";
      at: string;
      reason: OccurrenceReason;
      blockingRunId: string | null;
    };

/** The API already interleaves; this only reshapes. */
export function historyItems(
  history: readonly (RunHistoryEntry | OccurrenceHistoryEntry)[],
): HistoryItem[] {
  return history.map((entry) => {
    if (isRunEntry(entry)) {
      return { kind: "run", at: entry.at, runId: entry.run_id, status: entry.status };
    }
    return {
      kind: "occurrence",
      at: entry.at,
      reason: entry.reason,
      blockingRunId: entry.blocking_run_id ?? null,
    };
  });
}

function isRunEntry(entry: RunHistoryEntry | OccurrenceHistoryEntry): entry is RunHistoryEntry {
  return "run_id" in entry;
}

export function runHref(runId: string): string {
  return `/runs/${runId}`;
}

export type OverlapBanner = {
  story: string;
  blockingRunId: string;
  openHref: string;
  openLabel: string;
  runNowLabel: string;
};

export function overlapBanner(latest: OccurrenceRecord): OverlapBanner | null {
  if (latest.reason !== "overlap" || latest.blocking_run_id == null) {
    return null;
  }
  return {
    story: holeStory("overlap"),
    blockingRunId: latest.blocking_run_id,
    openHref: runHref(latest.blocking_run_id),
    openLabel: "Open the Run that blocked it",
    runNowLabel: "Run it now instead",
  };
}

export function runNowRefusal(error: unknown): string | null {
  if (error === null || error === undefined) {
    return null;
  }
  const code =
    typeof error === "object" && error !== null && "code" in error ? error.code : undefined;
  if (code === "schedule_run_active") {
    return "A Run of this Schedule is still going.";
  }
  if (typeof code === "string" && code === "needs_values") {
    return "This Schedule is missing values.";
  }
  return "Something went wrong. Try again in a moment.";
}

export type NeedsValuesBanner = {
  tone: "bad";
  names: string[];
  setValuesHref: string;
  setValuesLabel: string;
};

export function needsValuesBanner(input: {
  state: "active" | "paused" | "needs_values";
  missingVariableNames: readonly string[];
  workflowId: string;
  scheduleId: string;
}): NeedsValuesBanner | null {
  if (input.state !== "needs_values") {
    return null;
  }
  return {
    tone: "bad",
    names: [...input.missingVariableNames],
    setValuesHref: editSchedulePath(input.workflowId, input.scheduleId),
    setValuesLabel: "Set values",
  };
}

export function enabledPatch(enabled: boolean): { enabled: boolean } {
  return { enabled };
}
