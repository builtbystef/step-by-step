import {
  getWorkflowDraft,
  getWorkflowSelectorDrift,
  getWorkflowVersion,
  type WorkflowDocument,
} from "@step-by-step/api-client";

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

/**
 * One published document, for the editor showing a past Version.
 *
 * Keyed by its number and never invalidated: a Version is immutable, so the
 * one thing this cache can never hold is a stale answer.
 */

export function versionDocumentKey(orgId: string, workflowId: string, version: number) {
  return ["workflow-version", orgId, workflowId, version] as const;
}

export function versionDocumentQuery(orgId: string, workflowId: string, version: number | null) {
  return {
    queryKey: versionDocumentKey(orgId, workflowId, version ?? 0),
    enabled: version !== null,
    queryFn: async (): Promise<WorkflowDocument> => {
      const { data, error } = await getWorkflowVersion({
        path: { workflow_id: workflowId, number: version ?? 0 },
      });
      if (error) throw error;
      return data;
    },
  };
}

/**
 * Which Steps have been drifting in recent Runs, for the editor's badges.
 *
 * Its own key, because a save of the Draft does not change what recent Runs
 * did, and a test Run finishing does.
 */

export function selectorDriftKey(orgId: string, workflowId: string) {
  return ["workflow-selector-drift", orgId, workflowId] as const;
}

export function selectorDriftQuery(orgId: string, workflowId: string) {
  return {
    queryKey: selectorDriftKey(orgId, workflowId),
    queryFn: async (): Promise<ReadonlySet<string>> => {
      const { data, error } = await getWorkflowSelectorDrift({
        path: { workflow_id: workflowId },
      });
      if (error) throw error;
      return new Set(data.drifted_step_ids);
    },
  };
}
