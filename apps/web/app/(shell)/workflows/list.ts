import type { WorkflowSort } from "@step-by-step/api-client";

/**
 * What the Workflows list decides about itself before it draws anything.
 *
 * The endpoint always supports searching and sorting; the screen offers them
 * only once a list is long enough that scrolling has stopped working. That
 * threshold is `7mfxzj`'s, and it is a decision rather than a layout detail,
 * so it is read back here rather than buried in a condition.
 */

/** The list a person can still scan. From here up, they need the controls. */
export const SEARCH_AND_SORT_FROM = 40;

/**
 * How many rows a page asks for — the threshold exactly.
 *
 * That is what makes the rule answerable from the first page alone: a full
 * page means there are at least this many Workflows, and a short one means
 * there are fewer. Any other page size would need a count nobody is asking
 * the database for.
 */
export const PAGE_SIZE = SEARCH_AND_SORT_FROM;

/**
 * Whether the search box and the sort control render.
 *
 * They stay while a search is on, however few rows it left: controls that
 * vanished under the words being typed into them would be unusable.
 */
export function offersSearchAndSort(loaded: number, searching: boolean): boolean {
  return searching || loaded >= SEARCH_AND_SORT_FROM;
}

export type SortOption = {
  value: WorkflowSort;
  label: string;
};

/** The three orders, worded for a person rather than for the query string. */
export const SORT_OPTIONS: readonly SortOption[] = [
  { value: "activity", label: "Last active" },
  { value: "name", label: "Name" },
  { value: "created", label: "Newest" },
];
