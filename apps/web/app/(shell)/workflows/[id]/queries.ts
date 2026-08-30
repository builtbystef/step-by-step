import {
  getWorkflow,
  getWorkflowDraftDiff,
  listWorkflowVersions,
  type DraftComparison,
  type VersionSummary,
  type WorkflowSummary,
} from "@step-by-step/api-client";

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

export function versionsKey(orgId: string, workflowId: string) {
  return ["workflow-versions", orgId, workflowId] as const;
}

export function versionsQuery(orgId: string, workflowId: string) {
  return {
    queryKey: versionsKey(orgId, workflowId),
    queryFn: async (): Promise<VersionSummary[]> => {
      const { data, error } = await listWorkflowVersions({ path: { workflow_id: workflowId } });
      if (error) throw error;
      return data;
    },
  };
}

export function draftDiffKey(orgId: string, workflowId: string) {
  return ["workflow-draft-diff", orgId, workflowId] as const;
}

export function draftDiffQuery(orgId: string, workflowId: string, enabled: boolean) {
  return {
    queryKey: draftDiffKey(orgId, workflowId),
    enabled,
    queryFn: async (): Promise<DraftComparison> => {
      const { data, error } = await getWorkflowDraftDiff({ path: { workflow_id: workflowId } });
      if (error) throw error;
      return data;
    },
  };
}
