import type { RunStatus, RunTrigger } from "@step-by-step/api-client";

export const COLUMNS = [
  "status",
  "workflow",
  "trigger",
  "started",
  "duration",
  "id",
  "action",
] as const;

export type Column = (typeof COLUMNS)[number];

export function columnsOf(workflowId: string | undefined): readonly Column[] {
  return workflowId === undefined ? COLUMNS : COLUMNS.filter((column) => column !== "workflow");
}

export const GLOBAL_EMPTY = {
  absence: "Nothing has run yet",
  whatFillsIt: "Runs appear here whether you start them by hand, on a schedule, or as a batch.",
  action: "Go to Workflows",
} as const;

export const WORKFLOW_EMPTY = {
  absence: "This Workflow has not run yet",
  whatFillsIt: "Start a Run of the published Version.",
  action: "Run",
} as const;

export const FILTERED_EMPTY = "No Run matches these filters.";

export function hasListFilter(filters: Record<string, string>): boolean {
  return (filters.status ?? "") !== "" || (filters.trigger ?? "") !== "";
}

export type ListKind = "loading" | "empty" | "filtered" | "rows";

export function listKind(opts: {
  loaded: boolean;
  itemCount: number;
  filters: Record<string, string>;
}): ListKind {
  if (!opts.loaded && opts.itemCount === 0) {
    return "loading";
  }
  if (opts.itemCount > 0) {
    return "rows";
  }
  return hasListFilter(opts.filters) ? "filtered" : "empty";
}

export function runHref(id: string): string {
  return `/runs/${id}`;
}

export type RowAction = "take-control" | "open";

export function rowAction(status: RunStatus): RowAction {
  return status === "waiting_for_human" ? "take-control" : "open";
}

export function startedAt(run: { started_at: string | null; queued_at: string }): string {
  return run.started_at ?? run.queued_at;
}

export function runDurationMs(
  run: { started_at: string | null; ended_at: string | null },
  now: Date = new Date(),
): number | null {
  if (run.started_at === null) {
    return null;
  }
  const end = run.ended_at === null ? now.getTime() : Date.parse(run.ended_at);
  const elapsed = end - Date.parse(run.started_at);
  return Number.isNaN(elapsed) ? null : Math.max(0, elapsed);
}

/* The first UUID group is plenty to tell Runs apart at a glance; the full id
   stays available as the cell's title. */
export function shortRunId(id: string): string {
  return id.split("-")[0] ?? id;
}

export function triggerLabel(trigger: RunTrigger): string {
  return trigger;
}

export type FilterOption = { value: string; label: string };

export const STATUS_FILTERS: readonly FilterOption[] = [
  { value: "", label: "Any status" },
  { value: "queued", label: "queued" },
  { value: "running", label: "running" },
  { value: "waiting_for_human", label: "needs you" },
  { value: "succeeded", label: "succeeded" },
  { value: "failed", label: "failed" },
  { value: "cancelled", label: "cancelled" },
];

export const TRIGGER_FILTERS: readonly FilterOption[] = [
  { value: "", label: "Any trigger" },
  { value: "manual", label: "manual" },
  { value: "schedule", label: "schedule" },
  { value: "batch", label: "batch" },
  { value: "test", label: "test" },
];
