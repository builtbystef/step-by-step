"use client";

import { useParams } from "next/navigation";

import { BatchesList } from "./batches-list";

/**
 * Workflow ▸ Batches — the only home for a list of Batches, now that a global
 * Batches index is refused.
 */
export default function BatchesTab() {
  const params = useParams<{ id: string }>();

  return <BatchesList workflowId={params.id} />;
}
