import { listRuns, type RunPage, type RunStatus, type RunTrigger } from "@step-by-step/api-client";

import { RUNS_KEY } from "@/lib/attention";
import { PAGE_SIZE } from "@/lib/cursor-list";

/**
 * The Runs list as server state: one key per Organization and per filter,
 * paged by the cursor the endpoint cuts. The path is `RUNS_KEY` so starting
 * or cancelling a Run, which invalidates that prefix, reaches every variant.
 */

export const RUNS_PATH = RUNS_KEY[0];

export async function fetchRunPage(
  filters: Record<string, string>,
  cursor: string | null,
  limit: number = PAGE_SIZE,
): Promise<RunPage> {
  const { data, error } = await listRuns({
    query: {
      limit,
      ...(cursor === null ? {} : { cursor }),
      ...(filters.workflow_id === undefined || filters.workflow_id === ""
        ? {}
        : { workflow_id: filters.workflow_id }),
      ...(filters.status === undefined || filters.status === ""
        ? {}
        : { status: filters.status as RunStatus }),
      ...(filters.trigger === undefined || filters.trigger === ""
        ? {}
        : { trigger: filters.trigger as RunTrigger }),
    },
  });
  if (error) throw error;
  return data ?? { items: [] };
}
