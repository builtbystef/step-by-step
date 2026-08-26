/**
 * How Settings talks about the Workflows that bind to a Secret.
 *
 * The list shows "used by N workflows" with the names; the delete
 * confirmation names them too, then proceeds — informing, never blocking.
 */

export type NamedWorkflow = { workflow_name: string };

/** "used by N workflows · Name, Name", counted in Workflows. */
export function usedBySummary(usedBy: readonly NamedWorkflow[]): string {
  const names = usedBy.map((row) => row.workflow_name);
  const count = names.length;
  const howMany = `used by ${String(count)} workflow${count === 1 ? "" : "s"}`;
  return names.length === 0 ? howMany : `${howMany} · ${names.join(", ")}`;
}

/** What the delete confirmation says before the row is removed anyway. */
export function deleteConsequence(secretName: string, usedBy: readonly NamedWorkflow[]): string {
  const names = usedBy.map((row) => row.workflow_name);
  const who =
    names.length === 0
      ? "No Workflow uses it."
      : names.length === 1
        ? `${names[0]} uses it.`
        : `${names.join(", ")} use it.`;
  return `${who} ${secretName} and every member's Personal Override will be deleted.`;
}
