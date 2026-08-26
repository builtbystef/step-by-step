import {
  listAllSchedules,
  runScheduleNow,
  updateSchedule,
  type ScheduleSummary,
} from "@step-by-step/api-client";

import { enabledPatch } from "./presentation";

export { scheduleDetailKey, scheduleDetailQuery } from "../workflows/[id]/schedules/queries";

/**
 * The instance-wide Schedules list. Paging and the workflowId contract are
 * the shell spec's slice; this key is the rows the table draws.
 */

export function schedulesKey(orgId: string) {
  return ["schedules", orgId] as const;
}

export function schedulesQuery(orgId: string) {
  return {
    queryKey: schedulesKey(orgId),
    queryFn: async (): Promise<ScheduleSummary[]> => {
      const { data, error } = await listAllSchedules();
      if (error) throw error;
      return data?.items ?? [];
    },
  };
}

export async function patchEnabled(scheduleId: string, enabled: boolean): Promise<ScheduleSummary> {
  const { data, error } = await updateSchedule({
    path: { schedule_id: scheduleId },
    body: enabledPatch(enabled),
  });
  if (error) throw error;
  if (data === undefined) {
    throw new Error("empty patch");
  }
  return data;
}

export async function runNow(scheduleId: string): Promise<{ run_id: string }> {
  const { data, error } = await runScheduleNow({ path: { schedule_id: scheduleId } });
  if (error) throw error;
  if (data === undefined) {
    throw new Error("empty run-now");
  }
  return data;
}
