import {
  getWorkflowDraft,
  getWorkflowSelectorDrift,
  getWorkflowVersion,
  type WorkflowDocument,
} from "@step-by-step/api-client";

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
