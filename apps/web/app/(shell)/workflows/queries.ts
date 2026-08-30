import {
  listWorkflows,
  type WorkflowPage,
  type WorkflowSort,
  type WorkflowSummary,
} from "@step-by-step/api-client";

import { PAGE_SIZE } from "./list";

export type WorkflowFilters = {
  q: string;
  sort: WorkflowSort;
};

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

export function rowsOf(pages: WorkflowPage[] | undefined): WorkflowSummary[] {
  return (pages ?? []).flatMap((page) => page.items);
}
