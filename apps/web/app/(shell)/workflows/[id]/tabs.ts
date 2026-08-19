/**
 * The Workflow page's four tabs.
 *
 * Each is a URL segment rather than a piece of component state, so a tab is
 * linkable, a reload lands where it left off, and the back button walks the
 * tabs instead of leaving the Workflow. The bare Workflow address is not a
 * fifth place: it redirects to the Editor, which is what `tabAt` says about it.
 */

export type WorkflowTab = {
  label: string;
  segment: string;
};

/** The tab a Workflow opens on, and the one its bare address redirects to. */
export const EDITOR: WorkflowTab = { label: "Editor", segment: "editor" };

export const WORKFLOW_TABS: readonly WorkflowTab[] = [
  EDITOR,
  { label: "Runs", segment: "runs" },
  { label: "Schedules", segment: "schedules" },
  { label: "Batches", segment: "batches" },
];

/** Where a Workflow's tab lives. */
export function tabPath(workflowId: string, tab: WorkflowTab): string {
  return `/workflows/${workflowId}/${tab.segment}`;
}

/** Where a Workflow is, before a tab is named. */
export function workflowPath(workflowId: string): string {
  return `/workflows/${workflowId}`;
}

/**
 * The tab an address is on, or nothing when the address is not a Workflow's.
 *
 * A Workflow with no segment answers the Editor rather than nothing: it is the
 * address the redirect resolves, and a header that rendered no tab as current
 * for the instant before that redirect would flicker.
 */
export function tabAt(pathname: string): WorkflowTab | null {
  const [, section, id, segment, ...rest] = pathname.split("?")[0]?.split("/") ?? [];
  if (section !== "workflows" || !id || rest.length > 0) {
    return null;
  }
  if (segment === undefined || segment === "") {
    return EDITOR;
  }
  return WORKFLOW_TABS.find((tab) => tab.segment === segment) ?? null;
}
