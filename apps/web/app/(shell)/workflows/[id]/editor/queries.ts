import { getWorkflowDraft, type WorkflowDocument } from "@step-by-step/api-client";

/**
 * The Draft this editor edits: one document, under a key of its own.
 *
 * Separate from the Workflow's own key, because they change for different
 * reasons — a rename touches the row and a save touches the document — and a
 * save that had to refetch the header as well would redraw a name nobody
 * changed.
 */

export function draftKey(orgId: string, workflowId: string) {
  return ["workflow-draft", orgId, workflowId] as const;
}

export function draftQuery(orgId: string, workflowId: string) {
  return {
    queryKey: draftKey(orgId, workflowId),
    queryFn: async (): Promise<WorkflowDocument> => {
      const { data, error } = await getWorkflowDraft({ path: { workflow_id: workflowId } });
      if (error) throw error;
      return data;
    },
  };
}
