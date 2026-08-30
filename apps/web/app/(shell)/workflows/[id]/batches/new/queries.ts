import {
  getBatch,
  getWorkflow,
  getWorkflowVersion,
  listBatches,
  type BatchDetail,
  type BatchSummary,
  type Variable,
} from "@step-by-step/api-client";

export function workflowBatchesKey(orgId: string, workflowId: string) {
  return ["workflow-batches", orgId, workflowId] as const;
}

export function workflowBatchesQuery(orgId: string, workflowId: string) {
  return {
    queryKey: workflowBatchesKey(orgId, workflowId),
    queryFn: async (): Promise<BatchSummary[]> => {
      const { data, error } = await listBatches({ query: { workflow_id: workflowId } });
      if (error) throw error;
      return data?.items ?? [];
    },
  };
}

export async function loadBatch(batchId: string): Promise<BatchDetail> {
  const { data, error } = await getBatch({ path: { batch_id: batchId } });
  if (error) throw error;
  return data;
}

export async function loadPublishedVariables(workflowId: string): Promise<Variable[]> {
  const { data, error } = await getWorkflow({ path: { workflow_id: workflowId } });
  if (error) throw error;
  const version = data.published_version ?? null;
  if (version === null) {
    return [];
  }
  const document = await getWorkflowVersion({
    path: { workflow_id: workflowId, number: version },
  });
  if (document.error) throw document.error;
  return document.data.variables ?? [];
}
