import { describe, expect, it } from "vitest";

import { LEAVE_PROMPT, shouldAskBeforeLeave } from "./leave";

const EDITOR = "/workflows/3f1a/editor";
const RUNS = "/workflows/3f1a/runs";
const OTHER_EDITOR = "/workflows/9c2b/editor";

describe("the unsaved-edits guard", () => {
  it("asks before leaving the Editor tab with unsaved edits", () => {
    expect(shouldAskBeforeLeave(true, EDITOR, RUNS)).toBe(true);
    expect(shouldAskBeforeLeave(true, EDITOR, "/workflows/3f1a/schedules")).toBe(true);
    expect(shouldAskBeforeLeave(true, EDITOR, "/workflows/3f1a/batches")).toBe(true);
    expect(shouldAskBeforeLeave(true, EDITOR, "/workflows")).toBe(true);
    expect(shouldAskBeforeLeave(true, EDITOR, OTHER_EDITOR)).toBe(true);
  });

  it("keeps every edit when the next address is still this Editor", () => {
    expect(shouldAskBeforeLeave(true, EDITOR, EDITOR)).toBe(false);
    expect(shouldAskBeforeLeave(true, EDITOR, `${EDITOR}?version=2`)).toBe(false);
    expect(shouldAskBeforeLeave(true, EDITOR, "/workflows/3f1a")).toBe(false);
  });

  it("raises the browser's own warning when the tab is closing with unsaved edits", () => {
    expect(shouldAskBeforeLeave(true, EDITOR, null)).toBe(true);
  });

  it("has nothing to warn about after a save or a discard", () => {
    expect(shouldAskBeforeLeave(false, EDITOR, RUNS)).toBe(false);
    expect(shouldAskBeforeLeave(false, EDITOR, null)).toBe(false);
  });

  it("lives on the Editor tab and nowhere else", () => {
    expect(shouldAskBeforeLeave(true, RUNS, "/workflows")).toBe(false);
    expect(shouldAskBeforeLeave(true, "/runs", "/workflows")).toBe(false);
    expect(LEAVE_PROMPT.length).toBeGreaterThan(0);
  });
});
