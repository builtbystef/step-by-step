"use client";

import { useParams } from "next/navigation";

import { SchedulesList } from "../../../schedules/schedules-list";

export default function SchedulesTab() {
  const params = useParams<{ id: string }>();

  return <SchedulesList workflowId={params.id} />;
}
