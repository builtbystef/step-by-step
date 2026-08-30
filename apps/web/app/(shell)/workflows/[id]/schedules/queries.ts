import {
  getInstance,
  getSchedule,
  listRuns,
  previewSchedule,
  type RunSummary,
  type ScheduleDetail,
} from "@step-by-step/api-client";

import { previewBody } from "./creation";

export function instanceKey() {
  return ["instance"] as const;
}

export function instanceQuery() {
  return {
    queryKey: instanceKey(),
    staleTime: Number.POSITIVE_INFINITY,
    queryFn: async () => (await getInstance()).data ?? null,
  };
}

export function schedulePreviewKey(orgId: string, cron: string, timezone: string) {
  return ["schedule-preview", orgId, cron, timezone] as const;
}

export function schedulePreviewQuery(orgId: string, cron: string, timezone: string) {
  return {
    queryKey: schedulePreviewKey(orgId, cron, timezone),
    enabled: cron.trim() !== "" && timezone !== "",
    queryFn: async (): Promise<string[]> => {
      const { data, error } = await previewSchedule({ body: previewBody(cron, timezone) });
      if (error) throw error;
      return data.next_occurrences;
    },
  };
}

export function workflowRunsKey(orgId: string, workflowId: string) {
  return ["workflow-runs", orgId, workflowId] as const;
}

export function workflowRunsQuery(orgId: string, workflowId: string) {
  return {
    queryKey: workflowRunsKey(orgId, workflowId),
    queryFn: async (): Promise<RunSummary[]> => {
      const { data, error } = await listRuns({ query: { workflow_id: workflowId } });
      if (error) throw error;
      return data?.items ?? [];
    },
  };
}

export function scheduleDetailKey(orgId: string, scheduleId: string) {
  return ["schedule", orgId, scheduleId] as const;
}

export function scheduleDetailQuery(orgId: string, scheduleId: string) {
  return {
    queryKey: scheduleDetailKey(orgId, scheduleId),
    queryFn: async (): Promise<ScheduleDetail> => {
      const { data, error } = await getSchedule({ path: { schedule_id: scheduleId } });
      if (error) throw error;
      return data;
    },
  };
}
