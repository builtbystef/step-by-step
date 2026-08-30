import { describe, expect, it } from "vitest";

import { batchHref, listKind, rowCountLabel, WORKFLOW_EMPTY } from "./presentation";

import { OVERFLOW_ACTIONS, disabledReason } from "../../actions";
import { COPY } from "../../../../../lib/copy";

describe("the Batch row", () => {
  it("navigates to the batch progress screen", () => {
    expect(batchHref("bat-1")).toBe("/batches/bat-1");
  });

  it("names the row count without inventing a Batch-level status", () => {
    expect(rowCountLabel(0)).toBe("0 rows");
    expect(rowCountLabel(1)).toBe("1 row");
    expect(rowCountLabel(3)).toBe("3 rows");
  });
});

describe("the empty tab", () => {
  it("offers New batch as the Workflow's call to action", () => {
    expect(WORKFLOW_EMPTY.absence).toBe("This Workflow has no Batch yet");
    expect(WORKFLOW_EMPTY.action).toBe("New batch");
  });

  it("is empty, not filtered, when the Workflow has none", () => {
    expect(listKind({ loaded: true, itemCount: 0 })).toBe("empty");
    expect(listKind({ loaded: true, itemCount: 2 })).toBe("rows");
    expect(listKind({ loaded: false, itemCount: 0 })).toBe("loading");
  });

  it("disables New batch behind the shared sentence while never-published", () => {
    const action = OVERFLOW_ACTIONS.find((item) => item.label === WORKFLOW_EMPTY.action);
    expect(action?.key).toBe("new-batch");
    expect(disabledReason(action!, "never-published")).toBe(COPY.noPublishedVersion);
    expect(disabledReason(action!, "in-sync")).toBeNull();
  });
});
