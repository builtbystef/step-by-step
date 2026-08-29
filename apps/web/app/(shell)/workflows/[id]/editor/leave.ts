import { EDITOR, tabAt } from "../tabs";

/**
 * The unsaved-edits guard: it lives on the Editor tab, and nowhere else.
 *
 * Switching tab, clicking away through the sidebar, or leaving this Workflow
 * all ask first, because those unmount the edited copy. Staying on this
 * Editor — opening a Version of the same Workflow, the bare address that
 * redirects here — does not. Closing the browser is a leave of its own: the
 * browser's warning is what asks, and only while there is something to warn
 * about.
 *
 * Saving and discarding both clear the edited copy, so nothing remains to
 * ask about.
 */

/** What the in-app confirm asks. The browser's own warning carries no custom text. */
export const LEAVE_PROMPT = "This editor has changes you have not saved. Leave and lose them?";

/**
 * Whether leaving `from` for `to` should ask first.
 *
 * `to` is `null` when the browser tab is closing or reloading: there is no
 * next address, and the browser's own warning is the ask.
 */
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
