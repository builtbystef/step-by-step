export type NamedWorkflow = { workflow_name: string };

export function usedBySummary(usedBy: readonly NamedWorkflow[]): string {
  const names = usedBy.map((row) => row.workflow_name);
  const count = names.length;
  const howMany = `used by ${String(count)} workflow${count === 1 ? "" : "s"}`;
  return names.length === 0 ? howMany : `${howMany} · ${names.join(", ")}`;
}

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
