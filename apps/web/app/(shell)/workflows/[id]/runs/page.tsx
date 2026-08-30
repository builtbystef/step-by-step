"use client";

import { useParams } from "next/navigation";

import { RunsList } from "../../../runs/runs-list";

export default function RunsTab() {
  const params = useParams<{ id: string }>();

  return <RunsList workflowId={params.id} />;
}
