import { Placeholder } from "../placeholder";

/**
 * `/runs` — one reverse-chronological list of everything that has run.
 *
 * The list is one component with the Workflow's own Runs tab, and it arrives
 * with the slice that brings both.
 */
export default function RunsPage() {
  return (
    <>
      <h1 className="text-page">Runs</h1>
      <Placeholder>
        The Runs list arrives with its own slice: one reverse-chronological list, filterable by
        status and trigger.
      </Placeholder>
    </>
  );
}
