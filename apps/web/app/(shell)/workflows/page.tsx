import { Placeholder } from "../placeholder";

/**
 * `/workflows` — where signing in lands, and where the app has no dashboard to
 * land on instead.
 *
 * The list itself, its CRUD contract, and the first-run panel arrive with
 * `5rkj33`; the destination exists now so that the nav around it is not dead.
 */
export default function WorkflowsPage() {
  return (
    <>
      <h1 className="text-page">Workflows</h1>
      <Placeholder>
        The Workflows list arrives with its own slice, alongside creating, renaming, duplicating,
        and deleting a Workflow.
      </Placeholder>
    </>
  );
}
