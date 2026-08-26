"use client";

import { SchedulesList } from "./schedules-list";

/**
 * `/schedules` — everything that runs on a clock.
 *
 * The list is one component with the Workflow's own Schedules tab: this page
 * mounts it with no Workflow id.
 */
export default function SchedulesPage() {
  return (
    <>
      <h1 className="text-page">Schedules</h1>
      <SchedulesList />
    </>
  );
}
