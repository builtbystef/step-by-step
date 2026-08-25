import type { RunRecord, StepResultRecord } from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import { applyRunEvent, emptySnapshot, type CockpitSnapshot } from "./events";
import { clock, stepRailBadges } from "./presentation";

/**
 * A live Run's rail ticks from SSE without a reload: step.started opens a
 * Step, step.finished stamps its duration and badges. Reconnect is a REST
 * refetch; these events only advance what the refetch already holds.
 */

const START = "2026-08-25T12:00:00.000Z";
const T = (seconds: number) => new Date(Date.parse(START) + seconds * 1000).toISOString();

function run(overrides: Partial<RunRecord> = {}): RunRecord {
  return {
    id: "run-1",
    workflow_id: "wf-1",
    version_number: 1,
    draft_snapshot: null,
    is_test: false,
    trigger: "manual",
    status: "running",
    failure_reason: null,
    failure_detail: null,
    variables: {},
    timeout_ms: 1_800_000,
    worker_id: "worker-a",
    worker_vnc_endpoint: null,
    heartbeat_at: T(0),
    cancel_requested_at: null,
    pause_requested_at: null,
    takeover_deadline_at: null,
    auto_handback_disabled: false,
    queued_at: T(0),
    started_at: T(0),
    ended_at: null,
    automation_ms: 0,
    ...overrides,
  };
}

function snapshot(overrides: Partial<CockpitSnapshot> = {}): CockpitSnapshot {
  return {
    ...emptySnapshot(run()),
    ...overrides,
  };
}

describe("a live Run's rail", () => {
  it("ticks through Steps as step.started and step.finished arrive, with duration and badges", () => {
    let state = snapshot();

    state = applyRunEvent(state, {
      type: "step.started",
      data: { run_id: "run-1", step_id: "s1", position: 0, at: T(1) },
    });
    expect(state.inFlight).toEqual({ stepId: "s1", position: 0, startedAt: T(1) });
    expect(state.stepResults).toEqual([]);

    state = applyRunEvent(state, {
      type: "step.finished",
      data: {
        run_id: "run-1",
        step_id: "s1",
        status: "passed",
        matched_candidate_rank: 2,
        candidate_count: 5,
        completed_by_human: false,
        extracted_count: 3,
        at: T(4),
      },
    });

    expect(state.inFlight).toBeNull();
    const finished = state.stepResults[0];
    expect(finished?.step_id).toBe("s1");
    expect(finished?.status).toBe("passed");
    expect(finished?.matched_candidate_rank).toBe(2);
    expect(finished?.candidate_count).toBe(5);
    expect(finished?.extracted_value).toEqual([{}, {}, {}]);
    expect(
      clock(Date.parse(finished?.ended_at ?? "") - Date.parse(finished?.started_at ?? "")),
    ).toBe("0:03");
    expect(stepRailBadges(finished as StepResultRecord).map((badge) => badge.label)).toContain(
      "found on candidate 3/5",
    );

    state = applyRunEvent(state, {
      type: "step.started",
      data: { run_id: "run-1", step_id: "s2", position: 1, at: T(4) },
    });
    expect(state.inFlight?.stepId).toBe("s2");
    expect(state.stepResults).toHaveLength(1);
  });

  it("closes a cancelling Run onto the terminal banner when run.status arrives", () => {
    let state = snapshot({
      run: run({ cancel_requested_at: T(5), status: "running" }),
      inFlight: { stepId: "s3", position: 2, startedAt: T(4) },
    });

    state = applyRunEvent(state, {
      type: "run.status",
      data: { run_id: "run-1", status: "cancelled", at: T(8) },
    });

    expect(state.run.status).toBe("cancelled");
    expect(state.run.ended_at).toBe(T(8));
    expect(state.inFlight).toBeNull();
  });

  it("opens and closes control intervals from control events, so the timeline can render without a refetch", () => {
    let state = snapshot();
    state = applyRunEvent(state, {
      type: "control",
      data: { run_id: "run-1", phase: "waiting", at: T(10) },
    });
    expect(state.intervals).toEqual([
      expect.objectContaining({ kind: "waiting", started_at: T(10), ended_at: null }),
    ]);

    state = applyRunEvent(state, {
      type: "control",
      data: { run_id: "run-1", phase: "human", at: T(16) },
    });
    expect(state.intervals[0]?.ended_at).toBe(T(16));
    expect(state.intervals[1]).toEqual(
      expect.objectContaining({ kind: "human", started_at: T(16), ended_at: null }),
    );
  });

  it("keeps only later log lines on a log event, matching the REST after_seq read", () => {
    let state = snapshot({
      logs: [{ seq: 1, step_id: "s1", level: "info", text: "one", at: T(1) }],
    });
    state = applyRunEvent(state, {
      type: "log",
      data: { run_id: "run-1", seq: 2, step_id: "s1", level: "info", text: "two", at: T(2) },
    });
    expect(state.logs.map((line) => line.seq)).toEqual([1, 2]);
  });
});
