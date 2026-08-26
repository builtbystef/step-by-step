import { getBatch, getBatchOutput, getRunOutput, type BatchDetail } from "@step-by-step/api-client";

/**
 * The batch view's server state: the detail a reconnect refetches, the
 * uniform Output table, and a succeeded row's assembled extract.
 */

export function batchKey(orgId: string, batchId: string) {
  return ["batch", orgId, batchId] as const;
}

export function batchQuery(orgId: string, batchId: string) {
  return {
    queryKey: batchKey(orgId, batchId),
    retry: false,
    refetchOnWindowFocus: false,
    queryFn: async (): Promise<BatchDetail> => {
      const { data, error } = await getBatch({ path: { batch_id: batchId } });
      if (error) throw error;
      return data;
    },
  };
}

export function batchOutputQuery(orgId: string, batchId: string, enabled: boolean) {
  return {
    queryKey: ["batch-output", orgId, batchId] as const,
    enabled,
    retry: false,
    refetchOnWindowFocus: false,
    queryFn: async (): Promise<unknown> => {
      const { data, error } = await getBatchOutput({
        path: { batch_id: batchId },
        query: { format: "json" },
      });
      if (error) throw error;
      return data;
    },
  };
}

export function rowOutputQuery(orgId: string, runId: string | null, enabled: boolean) {
  return {
    queryKey: ["batch-row-output", orgId, runId ?? ""] as const,
    enabled: enabled && runId !== null,
    retry: false,
    refetchOnWindowFocus: false,
    queryFn: async (): Promise<unknown> => {
      if (runId === null) {
        return null;
      }
      const { data, error } = await getRunOutput({
        path: { run_id: runId },
        query: { format: "json" },
      });
      if (error) throw error;
      return data;
    },
  };
}
