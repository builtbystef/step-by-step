/**
 * The Workflow's Batches tab: where a row goes, what an empty Workflow
 * says, and how a row names its size. The page draws these. It does not
 * re-decide them.
 *
 * There is no global Batches list. This tab is the list's only home, so a
 * Workflow id is not a prop that changes three things — it is the list.
 */

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
