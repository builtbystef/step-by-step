"use client";

import { SchedulesTable } from "./schedules-table";

import { useActiveOrganization } from "../use-active-organization";

/**
 * `/schedules` — everything that runs on a clock.
 *
 * The table content is this slice. The one-component/two-route wiring with
 * the Workflow's Schedules tab is the shell spec's.
 */
export default function SchedulesPage() {
  const { active } = useActiveOrganization();

  if (active === null) {
    return null;
  }

  return (
    <>
      <h1 className="text-page">Schedules</h1>
      <SchedulesTable orgId={active.id} />
    </>
  );
}
