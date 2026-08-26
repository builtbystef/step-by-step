import {
  getBatch,
  listBatches,
  type BatchDetail,
  type BatchSummary,
} from "@step-by-step/api-client";

/**
 * The Workflow's past Batches, for "Copy from a past Batch".
 *
 * Its own key, because creating a Batch is the only thing that changes it
 * and the creation page should not refetch a Workflow header that did not
 * move.
 */

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
