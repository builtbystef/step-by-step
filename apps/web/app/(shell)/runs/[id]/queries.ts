import {
  getRun,
  getRunOutput,
  getWorkflow,
  getWorkflowVersion,
  listRunLogs,
  type LogLine,
  type RunDetail,
  type WorkflowDocument,
  type WorkflowSummary,
} from "@step-by-step/api-client";

/**
 * The cockpit's server state: the Run detail a reconnect refetches, the log
 * lines beside it, the assembled extract output, the Workflow's name, and the
 * Version document the rail reads labels and sentences from.
 */

export function runKey(orgId: string, runId: string) {
  return ["run", orgId, runId] as const;
}

export type CockpitLoad = {
  detail: RunDetail;
  logs: LogLine[];
};

export function runQuery(orgId: string, runId: string) {
  return {
    queryKey: runKey(orgId, runId),
    retry: false,
    refetchOnWindowFocus: false,
    queryFn: async (): Promise<CockpitLoad> => {
      const detail = await getRun({ path: { run_id: runId } });
      if (detail.error) throw detail.error;
      const logs = await listRunLogs({ path: { run_id: runId } });
      if (logs.error) throw logs.error;
      return { detail: detail.data, logs: logs.data ?? [] };
    },
  };
}

export function runOutputQuery(orgId: string, runId: string) {
  return {
    queryKey: ["run-output", orgId, runId] as const,
    retry: false,
    refetchOnWindowFocus: false,
    queryFn: async (): Promise<unknown> => {
      const { data, error } = await getRunOutput({
        path: { run_id: runId },
        query: { format: "json" },
      });
      if (error) throw error;
      return data;
    },
  };
}

export function runWorkflowQuery(orgId: string, workflowId: string, enabled: boolean) {
  return {
    queryKey: ["run-workflow", orgId, workflowId] as const,
    enabled,
    queryFn: async (): Promise<WorkflowSummary> => {
      const { data, error } = await getWorkflow({ path: { workflow_id: workflowId } });
      if (error) throw error;
      return data;
    },
  };
}

export function runVersionQuery(
  orgId: string,
  workflowId: string,
  version: number | null,
  enabled: boolean,
) {
  return {
    queryKey: ["run-version", orgId, workflowId, version ?? 0] as const,
    enabled: enabled && version !== null,
    queryFn: async (): Promise<WorkflowDocument> => {
      const { data, error } = await getWorkflowVersion({
        path: { workflow_id: workflowId, number: version ?? 0 },
      });
      if (error) throw error;
      return data;
    },
  };
}
