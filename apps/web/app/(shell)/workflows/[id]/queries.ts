import {
  getWorkflow,
  getWorkflowDraftDiff,
  listWorkflowVersions,
  type DraftComparison,
  type VersionSummary,
  type WorkflowSummary,
} from "@step-by-step/api-client";

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

/**
 * Every Version of this Workflow, for the header's dropdown.
 *
 * Its own key, because publishing is the only thing that changes it and a
 * Draft that is saved forty times on the way to one publish should not refetch
 * a list that did not move.
 */

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

/**
 * What publishing would change: the Draft measured against the latest Version.
 *
 * Only the publish modal asks for it, and only while it is open — a
 * comparison of two whole documents is not something to keep warm behind a
 * screen nobody opened.
 */

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
