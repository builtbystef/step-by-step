export function batchHref(id: string): string {
  return `/batches/${id}`;
}

export const WORKFLOW_EMPTY = {
  absence: "This Workflow has no Batch yet",
  whatFillsIt: "A Batch runs the published Version once per input row.",
  action: "New batch",
} as const;

export type ListKind = "loading" | "empty" | "rows";

export function listKind(opts: { loaded: boolean; itemCount: number }): ListKind {
  if (!opts.loaded && opts.itemCount === 0) {
    return "loading";
  }
  return opts.itemCount > 0 ? "rows" : "empty";
}

export function rowCountLabel(rowCount: number): string {
  return rowCount === 1 ? "1 row" : `${String(rowCount)} rows`;
}
