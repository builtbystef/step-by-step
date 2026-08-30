export type WorkflowTab = {
  label: string;
  segment: string;
};

export const EDITOR: WorkflowTab = { label: "Editor", segment: "editor" };

export const WORKFLOW_TABS: readonly WorkflowTab[] = [
  EDITOR,
  { label: "Runs", segment: "runs" },
  { label: "Schedules", segment: "schedules" },
  { label: "Batches", segment: "batches" },
];

export function tabPath(workflowId: string, tab: WorkflowTab): string {
  return `/workflows/${workflowId}/${tab.segment}`;
}

export function newBatchPath(workflowId: string): string {
  return `/workflows/${workflowId}/batches/new`;
}

export function newSchedulePath(workflowId: string): string {
  return `/workflows/${workflowId}/schedules/new`;
}

export function editSchedulePath(workflowId: string, scheduleId: string): string {
  return `/workflows/${workflowId}/schedules/${scheduleId}`;
}

export function workflowPath(workflowId: string): string {
  return `/workflows/${workflowId}`;
}

export function tabAt(pathname: string): WorkflowTab | null {
  const [, section, id, segment] = pathname.split("?")[0]?.split("/") ?? [];
  if (section !== "workflows" || !id) {
    return null;
  }
  if (segment === undefined || segment === "") {
    return EDITOR;
  }
  return WORKFLOW_TABS.find((tab) => tab.segment === segment) ?? null;
}
