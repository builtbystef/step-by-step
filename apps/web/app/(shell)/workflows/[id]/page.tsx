import { redirect } from "next/navigation";

import { EDITOR, tabPath } from "./tabs";

export default async function WorkflowPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(tabPath(id, EDITOR));
}
