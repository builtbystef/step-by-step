"use client";

import { useParams } from "next/navigation";

import { RunsList } from "../../../runs/runs-list";

/**
 * Workflow ▸ Runs — the global Runs list filtered to this Workflow, and the
 * same component rendering it (`<RunsList workflowId>`).
 */
export default function RunsTab() {
  const params = useParams<{ id: string }>();

  return <RunsList workflowId={params.id} />;
}
