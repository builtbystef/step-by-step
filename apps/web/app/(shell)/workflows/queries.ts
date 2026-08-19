import {
  listWorkflows,
  type WorkflowPage,
  type WorkflowSort,
  type WorkflowSummary,
} from "@step-by-step/api-client";

import { PAGE_SIZE } from "./list";

/**
 * The Workflows list as server state: one key per Organization and per filter,
 * paged by the cursor the endpoint cuts.
 *
 * The filters are part of the key rather than of the query function, so that a
 * search is its own cache entry and going back to the unfiltered list is
 * instant — and so that a create, a rename, or a delete invalidates every one
 * of them by naming the Organization alone.
 */

export type WorkflowFilters = {
  q: string;
  sort: WorkflowSort;
};

/** Everything this Organization's list holds, whatever is filtered. */
export function workflowsKey(orgId: string) {
  return ["workflows", orgId] as const;
}

export function filteredWorkflowsKey(orgId: string, filters: WorkflowFilters) {
  return [...workflowsKey(orgId), filters] as const;
}

export function workflowsQuery(orgId: string, filters: WorkflowFilters) {
  return {
    queryKey: filteredWorkflowsKey(orgId, filters),
    queryFn: async ({ pageParam }: { pageParam: string | null }): Promise<WorkflowPage> => {
      const { data, error } = await listWorkflows({
        query: {
          q: filters.q,
          sort: filters.sort,
          limit: PAGE_SIZE,
          ...(pageParam === null ? {} : { cursor: pageParam }),
        },
      });
      if (error) throw error;
      return data ?? { items: [] };
    },
    initialPageParam: null as string | null,
    getNextPageParam: (last: WorkflowPage): string | null => last.next_cursor ?? null,
  };
}

/** Every row loaded so far, flattened out of the pages that carried them. */
export function rowsOf(pages: WorkflowPage[] | undefined): WorkflowSummary[] {
  return (pages ?? []).flatMap((page) => page.items);
}
