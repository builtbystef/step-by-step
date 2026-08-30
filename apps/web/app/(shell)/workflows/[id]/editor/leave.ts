import { EDITOR, tabAt } from "../tabs";

export const LEAVE_PROMPT = "This editor has changes you have not saved. Leave and lose them?";

export function shouldAskBeforeLeave(unsaved: boolean, from: string, to: string | null): boolean {
  if (!unsaved) {
    return false;
  }
  if (tabAt(from) !== EDITOR) {
    return false;
  }
  if (to === null) {
    return true;
  }
  return leavesThisEditor(from, to);
}

function leavesThisEditor(from: string, to: string): boolean {
  const fromId = workflowIdAt(from);
  const toId = workflowIdAt(to);
  return !(fromId !== null && fromId === toId && tabAt(to) === EDITOR);
}

function workflowIdAt(pathname: string): string | null {
  const [, section, id] = (pathname.split("?")[0] ?? "").split("/");
  if (section !== "workflows" || id === undefined || id === "") {
    return null;
  }
  return id;
}
