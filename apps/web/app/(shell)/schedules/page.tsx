import { Placeholder } from "../placeholder";

/**
 * `/schedules` — everything that runs on a clock.
 *
 * Like the Runs list, it is one component with the Workflow's own tab, and it
 * arrives with the slice that brings both.
 */
export default function SchedulesPage() {
  return (
    <>
      <h1 className="text-page">Schedules</h1>
      <Placeholder>
        The Schedules list arrives with its own slice: the recurrence in words, what is next due,
        and the Occurrences that did not fire.
      </Placeholder>
    </>
  );
}
