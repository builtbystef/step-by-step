"use client";

import { RunsList } from "./runs-list";

/**
 * `/runs` — one reverse-chronological list of everything that has run.
 *
 * The list is one component with the Workflow's own Runs tab: this page
 * mounts it with no Workflow id.
 */
export default function RunsPage() {
  return (
    <>
      <h1 className="text-page">Runs</h1>
      <RunsList />
    </>
  );
}
