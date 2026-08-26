import { listBatches, type BatchPage } from "@step-by-step/api-client";

import { PAGE_SIZE } from "@/lib/cursor-list";

/**
 * The Workflow's Batches list as server state. `workflow_id` is required:
 * there is no global Batches index, so this tab is the list's only home.
 */

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
