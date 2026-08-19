import { getWorkflow, type WorkflowSummary } from "@step-by-step/api-client";

/**
 * The one Workflow a Workflow page is about, under a key of its own.
 *
 * Its own key rather than a row plucked out of the list's cache: the page is
 * reachable by its address, so it has to be able to load without the list
 * ever having been rendered.
 */

export function workflowKey(orgId: string, workflowId: string) {
  return ["workflow", orgId, workflowId] as const;
}

export function workflowQuery(orgId: string, workflowId: string) {
  return {
    queryKey: workflowKey(orgId, workflowId),
    queryFn: async (): Promise<WorkflowSummary> => {
      const { data, error } = await getWorkflow({ path: { workflow_id: workflowId } });
      if (error) throw error;
      return data;
    },
  };
}
