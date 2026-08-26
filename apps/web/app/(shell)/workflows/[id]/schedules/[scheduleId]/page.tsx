"use client";

import { useParams } from "next/navigation";

import { ScheduleForm } from "../schedule-form";

import { useActiveOrganization } from "../../../../use-active-organization";

/**
 * Where an existing Schedule is edited. A cron the grammar cannot hold
 * opens in raw-cron mode with the expression intact.
 */

export default function EditSchedulePage() {
  const { active } = useActiveOrganization();
  const params = useParams<{ id: string; scheduleId: string }>();

  if (active === null) {
    return null;
  }

  return <ScheduleForm orgId={active.id} workflowId={params.id} scheduleId={params.scheduleId} />;
}
