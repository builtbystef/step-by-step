import type { WorkflowSort } from "@step-by-step/api-client";

export const SEARCH_AND_SORT_FROM = 40;

export const PAGE_SIZE = SEARCH_AND_SORT_FROM;

export function offersSearchAndSort(loaded: number, searching: boolean): boolean {
  return searching || loaded >= SEARCH_AND_SORT_FROM;
}

export type SortOption = {
  value: WorkflowSort;
  label: string;
};

export const SORT_OPTIONS: readonly SortOption[] = [
  { value: "activity", label: "Last active" },
  { value: "name", label: "Name" },
  { value: "created", label: "Newest" },
];
