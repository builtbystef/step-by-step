"use client";

import { useParams } from "next/navigation";

import { SchedulesList } from "../../../schedules/schedules-list";

/**
 * Workflow ▸ Schedules — the global Schedules list filtered to this Workflow,
 * and the same component rendering it (`<SchedulesList workflowId>`).
 */
export default function SchedulesTab() {
  const params = useParams<{ id: string }>();

  return <SchedulesList workflowId={params.id} />;
}
