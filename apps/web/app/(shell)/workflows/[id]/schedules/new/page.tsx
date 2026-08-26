"use client";

import { useParams } from "next/navigation";

import { ScheduleForm } from "../schedule-form";

import { useActiveOrganization } from "../../../../use-active-organization";

/**
 * Where a new Schedule of this Workflow is built: the sentence, the one-row
 * value set, then create.
 */

export default function NewSchedulePage() {
  const { active } = useActiveOrganization();
  const params = useParams<{ id: string }>();

  if (active === null) {
    return null;
  }

  return <ScheduleForm orgId={active.id} workflowId={params.id} />;
}
