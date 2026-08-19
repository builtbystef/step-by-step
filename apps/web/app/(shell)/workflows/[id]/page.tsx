import { redirect } from "next/navigation";

import { EDITOR, tabPath } from "./tabs";

/**
 * `/workflows/[id]` is not a place: it is the Workflow, and the Workflow opens
 * on its editor.
 *
 * A redirect rather than a fifth tab, so that every address the app links to
 * is one of the four and the back button walks tabs.
 */
export default async function WorkflowPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(tabPath(id, EDITOR));
}
