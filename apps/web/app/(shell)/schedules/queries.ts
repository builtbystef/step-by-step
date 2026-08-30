import {
  listAllSchedules,
  runScheduleNow,
  updateSchedule,
  type SchedulePage,
  type ScheduleSummary,
} from "@step-by-step/api-client";

import { enabledPatch } from "./presentation";

import { PAGE_SIZE } from "@/lib/cursor-list";

export { scheduleDetailKey, scheduleDetailQuery } from "../workflows/[id]/schedules/queries";

export const SCHEDULES_PATH = "/api/schedules";

export const SCHEDULES_KEY = [SCHEDULES_PATH] as const;

export async function fetchSchedulePage(
  filters: Record<string, string>,
  cursor: string | null,
  limit: number = PAGE_SIZE,
): Promise<SchedulePage> {
  const { data, error } = await listAllSchedules({
    query: {
      limit,
      ...(cursor === null ? {} : { cursor }),
      ...(filters.workflow_id === undefined || filters.workflow_id === ""
        ? {}
        : { workflow_id: filters.workflow_id }),
    },
  });
  if (error) throw error;
  return data ?? { items: [] };
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
