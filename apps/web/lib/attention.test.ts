import { describe, expect, it, vi } from "vitest";

import {
  ATTENTION_KEY,
  RUNS_KEY,
  attentionMessage,
  attentionRefetchInterval,
  formatDeadline,
  invalidateRunState,
  runsBadge,
} from "./attention";

describe("shell attention", () => {
  it("words one and several waiting Runs from the soonest entry", () => {
    expect(attentionMessage(1, "Invoice download — AcmeBank")).toBe(
      "Invoice download — AcmeBank is waiting for you",
    );
    expect(attentionMessage(3, "Invoice download — AcmeBank")).toBe(
      "3 Runs are waiting for you — the soonest is Invoice download — AcmeBank",
    );
  });

  it("counts down locally without claiming the Run timed out", () => {
    const now = Date.parse("2026-08-24T09:00:00Z");
    expect(formatDeadline("2026-08-24T09:01:01Z", now)).toBe("00:01:01");
    expect(formatDeadline("2026-08-24T09:00:00Z", now)).toBe("the deadline has passed");
  });

  it("polls only while visible and catches up on focus", () => {
    expect(attentionRefetchInterval("visible")).toBe(10_000);
    expect(attentionRefetchInterval("hidden")).toBe(false);
  });

  it("derives the nav count and its waiting-first tone", () => {
    expect(runsBadge({ waiting_count: 0, running_count: 0, queued_count: 0 })).toEqual({
      count: 0,
      tone: "in-flight",
    });
    expect(runsBadge({ waiting_count: 0, running_count: 2, queued_count: 3 })).toEqual({
      count: 5,
      tone: "in-flight",
    });
    expect(runsBadge({ waiting_count: 1, running_count: 2, queued_count: 3 })).toEqual({
      count: 6,
      tone: "waiting",
    });
  });

  it("invalidates attention and the Runs list together after any state change", async () => {
    const invalidateQueries = vi.fn().mockResolvedValue(undefined);

    await invalidateRunState({ invalidateQueries });

    expect(invalidateQueries).toHaveBeenCalledTimes(2);
    expect(invalidateQueries).toHaveBeenNthCalledWith(1, { queryKey: ATTENTION_KEY });
    expect(invalidateQueries).toHaveBeenNthCalledWith(2, { queryKey: RUNS_KEY });
  });
});
