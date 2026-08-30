import { listBatches, type BatchPage } from "@step-by-step/api-client";

import { PAGE_SIZE } from "@/lib/cursor-list";

export const BATCHES_PATH = "/api/batches";

export async function fetchBatchPage(
  workflowId: string,
  cursor: string | null,
  limit: number = PAGE_SIZE,
): Promise<BatchPage> {
  const { data, error } = await listBatches({
    query: {
      workflow_id: workflowId,
      limit,
      ...(cursor === null ? {} : { cursor }),
    },
  });
  if (error) throw error;
  return data ?? { items: [] };
}
