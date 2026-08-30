"use client";

import { useParams } from "next/navigation";

import { BatchesList } from "./batches-list";

export default function BatchesTab() {
  const params = useParams<{ id: string }>();

  return <BatchesList workflowId={params.id} />;
}
