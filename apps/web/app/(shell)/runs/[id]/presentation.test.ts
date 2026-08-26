import type {
  ArtifactRecord,
  ControlIntervalRecord,
  LogLine,
  RunRecord,
  StepResultRecord,
  Variable,
} from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import type { Step } from "../../workflows/[id]/editor/steps";

import {
  CANCEL_CONFIRM,
  candidateFates,
  cancellingBand,
  chipState,
  clock,
  driftBadgeLabel,
  driftChipLabel,
  driftedCount,
  elapsedMs,
  EMPTY_OUTPUT,
  outputDownloadHref,
  outputTable,
  panePlaceholder,
  recordCount,
  downloadCount,
  repickHref,
  runAgainValues,
  stepExpansion,
  stepRailBadges,
  terminalBanner,
  timeWithYouMs,
  timeline,
  type BannerInput,
} from "./presentation";

/**
 * The cockpit's decisions, read back without a DOM: the header chip and
 * drift wording, the timeline's proportions, the terminal sentences, cancel,
 * Run again's prefill, and the Output tab's table vs empty sentence. The page
 * draws these; it does not re-decide them.
 */

const START = "2026-08-25T12:00:00.000Z";
const T = (seconds: number) => new Date(Date.parse(START) + seconds * 1000).toISOString();

function run(overrides: Partial<RunRecord> = {}): RunRecord {
  return {
    id: "run-1",
    workflow_id: "wf-1",
    version_number: 3,
    draft_snapshot: null,
    is_test: false,
    trigger: "manual",
    status: "succeeded",
    failure_reason: null,
    failure_detail: null,
    variables: {},
    timeout_ms: 1_800_000,
    worker_id: "worker-a",
    worker_vnc_endpoint: null,
    heartbeat_at: T(39),
    cancel_requested_at: null,
    pause_requested_at: null,
    takeover_deadline_at: null,
    auto_handback_disabled: false,
    queued_at: T(0),
    started_at: T(0),
    ended_at: T(39),
    automation_ms: 19_000,
    ...overrides,
  };
}

function result(
  overrides: Partial<StepResultRecord> & Pick<StepResultRecord, "step_id">,
): StepResultRecord {
  return {
    id: `res-${overrides.step_id}`,
    position: 0,
    status: "passed",
    started_at: T(0),
    ended_at: T(1),
    matched_candidate_rank: 0,
    candidate_count: 1,
    completed_by_human: false,
    error_code: null,
    error_message: null,
    diagnostics: null,
    extracted_value: null,
    ...overrides,
  };
}

function clicking(id: string, label: string): Step {
  return {
    id,
    label,
    type: "click",
    payload: {
      target: {
        candidates: [
          { kind: "role", value: "Save" },
          { kind: "text", value: "Save" },
          { kind: "css", value: "button.primary" },
          { kind: "css", value: "#main > button:nth-child(1)" },
          { kind: "css", value: "form > button" },
        ],
      },
    },
  };
}

describe("the clock the cockpit reads", () => {
  it("writes elapsed the way the terminal banner does, unpadded minutes", () => {
    expect(clock(39_000)).toBe("0:39");
    expect(clock(0)).toBe("0:00");
    expect(clock(90_000)).toBe("1:30");
  });
});

describe("the status chip's state", () => {
  it("is the Run status, except a requested cancel which is cancelling until terminal", () => {
    expect(chipState(run({ status: "running", ended_at: null }))).toBe("running");
    expect(chipState(run({ status: "running", cancel_requested_at: T(10), ended_at: null }))).toBe(
      "cancelling",
    );
    expect(
      chipState(run({ status: "cancelled", cancel_requested_at: T(10), ended_at: T(12) })),
    ).toBe("cancelled");
    expect(chipState(run({ status: "waiting_for_human", ended_at: null }))).toBe(
      "waiting_for_human",
    );
  });
});

describe("selector drift in the header and on a Step", () => {
  it("counts a rank-3 match as one drifted Step, worded as the spec's chip and badge", () => {
    const results = [
      result({ step_id: "s1", position: 0, matched_candidate_rank: 0, candidate_count: 2 }),
      result({
        step_id: "s2",
        position: 1,
        matched_candidate_rank: 2,
        candidate_count: 5,
      }),
    ];

    expect(driftedCount(results)).toBe(1);
    expect(driftChipLabel(1)).toBe("⚠ 1 step drifted");
    expect(driftChipLabel(2)).toBe("⚠ 2 steps drifted");
    expect(driftChipLabel(0)).toBeNull();
    expect(driftBadgeLabel(2, 5)).toBe("found on candidate 3/5");
  });

  it("marks earlier candidates as died, the match, and the rest untried, and points Re-pick at the editor", () => {
    expect(candidateFates(5, 2)).toEqual(["died", "died", "matched", "untried", "untried"]);
    expect(repickHref("wf-1", "s2")).toBe("/workflows/wf-1/editor?repick=s2");
  });
});

describe("the timeline strip", () => {
  it("renders four interval kinds proportionally, with markers, from the intervals themselves", () => {
    const intervals: ControlIntervalRecord[] = [
      { id: "i1", kind: "automation", started_at: T(0), ended_at: T(10) },
      { id: "i2", kind: "waiting", started_at: T(10), ended_at: T(16) },
      { id: "i3", kind: "human", started_at: T(16), ended_at: T(27) },
      { id: "i4", kind: "verifying", started_at: T(27), ended_at: T(29) },
      { id: "i5", kind: "automation", started_at: T(29), ended_at: T(39) },
    ];

    const strip = timeline(intervals, new Date(T(39)));

    expect(strip.segments.map((segment) => segment.kind)).toEqual([
      "automation",
      "waiting",
      "human",
      "verifying",
      "automation",
    ]);
    expect(strip.segments.map((segment) => segment.durationMs)).toEqual([
      10_000, 6_000, 11_000, 2_000, 10_000,
    ]);
    const total = strip.segments.reduce((sum, segment) => sum + segment.flex, 0);
    expect(total).toBeCloseTo(1);
    expect(strip.segments[1]?.flex).toBeCloseTo(6 / 39);
    expect(strip.markers.map((marker) => marker.label)).toEqual([
      "paused",
      "you took control",
      "handed back",
      "resumed",
    ]);
  });
});

describe("a failed Step's expansion", () => {
  it("shows its error, its failure screenshot, and only its own log lines", () => {
    const step = clicking("s6", "Open Invoices");
    const failed = result({
      step_id: "s6",
      position: 5,
      status: "failed",
      matched_candidate_rank: null,
      candidate_count: 5,
      error_code: "no_candidate_resolved",
      error_message: "none of the 5 recorded candidates matched exactly one element",
    });
    const artifacts: ArtifactRecord[] = [
      {
        id: "shot-ok",
        step_id: "s1",
        kind: "screenshot",
        content_type: "image/png",
        size_bytes: 10,
        index: 0,
        created_at: T(1),
        filename: "s1.png",
      },
      {
        id: "shot-fail",
        step_id: "s6",
        kind: "screenshot",
        content_type: "image/png",
        size_bytes: 20,
        index: 1,
        created_at: T(20),
        filename: "s6.png",
      },
    ];
    const logs: LogLine[] = [
      { seq: 1, step_id: "s1", level: "info", text: "Click Save", at: T(1) },
      { seq: 2, step_id: "s6", level: "error", text: "selector missed", at: T(20) },
      { seq: 3, step_id: null, level: "info", text: "run ended", at: T(21) },
    ];

    const expansion = stepExpansion({
      workflowId: "wf-1",
      step,
      result: failed,
      artifacts,
      logs,
    });

    expect(expansion.error).toEqual({
      code: "no_candidate_resolved",
      message: "none of the 5 recorded candidates matched exactly one element",
    });
    expect(expansion.screenshots.map((shot) => shot.id)).toEqual(["shot-fail"]);
    expect(expansion.logs.map((line) => line.seq)).toEqual([2]);
    expect(expansion.repickHref).toBe("/workflows/wf-1/editor?repick=s6");
  });
});

describe("the terminal banner", () => {
  it("reads a seeded successful Run in the spec's exact pattern", () => {
    const results = Array.from({ length: 8 }, (_, position) =>
      result({
        step_id: `s${String(position + 1)}`,
        position,
        extracted_value: position === 7 ? Array.from({ length: 24 }, () => ({ n: 1 })) : null,
      }),
    );
    const artifacts: ArtifactRecord[] = [
      {
        id: "dl",
        step_id: "s3",
        kind: "download",
        content_type: "application/pdf",
        size_bytes: 100,
        index: 0,
        created_at: T(10),
        filename: "invoice.pdf",
      },
    ];
    const input: BannerInput = {
      run: run({ started_at: T(0), ended_at: T(39), status: "succeeded" }),
      results,
      artifacts,
      totalSteps: 8,
    };

    expect(recordCount(results)).toBe(24);
    expect(downloadCount(artifacts)).toBe(1);
    expect(terminalBanner(input)).toBe(
      "succeeded in 0:39 · 8 of 8 steps · 24 records · 1 download",
    );
  });

  it("names the failing step, the reason, and the skipped count", () => {
    const results = [
      ...Array.from({ length: 5 }, (_, position) =>
        result({ step_id: `s${String(position + 1)}`, position }),
      ),
      result({
        step_id: "s6",
        position: 5,
        status: "failed",
        error_code: "no_candidate_resolved",
        error_message: "missed",
        matched_candidate_rank: null,
      }),
      result({ step_id: "s7", position: 6, status: "skipped", started_at: null, ended_at: null }),
      result({ step_id: "s8", position: 7, status: "skipped", started_at: null, ended_at: null }),
    ];

    expect(
      terminalBanner({
        run: run({
          status: "failed",
          failure_reason: "step_failed",
          started_at: T(0),
          ended_at: T(20),
        }),
        results,
        artifacts: [],
        totalSteps: 8,
      }),
    ).toBe("failed at step 6 · step_failed · remaining 2 steps skipped");
  });
});

describe("cancel", () => {
  it("states the boundary rule, then the cancelling band for the in-flight Step", () => {
    expect(CANCEL_CONFIRM).toBe(
      "The Worker finishes the action it is on, then stops at the next Step boundary — it never stops mid-click.",
    );
    expect(cancellingBand(4)).toBe("cancelling — waiting for step 4 to reach a boundary");
  });

  it("drops the cancelling band once the terminal banner is the outcome", () => {
    const cancelling = run({
      status: "running",
      cancel_requested_at: T(10),
      ended_at: null,
    });
    expect(chipState(cancelling)).toBe("cancelling");
    expect(
      terminalBanner({
        run: cancelling,
        results: [],
        artifacts: [],
        totalSteps: 8,
      }),
    ).toBeNull();
    expect(
      terminalBanner({
        run: run({ status: "cancelled", cancel_requested_at: T(10), ended_at: T(12) }),
        results: [result({ step_id: "s1", position: 0 })],
        artifacts: [],
        totalSteps: 8,
      }),
    ).toMatch(/^cancelled /);
  });
});

describe("Run again", () => {
  it("prefills the dialog with this Run's Variable values, skipping secrets", () => {
    const declared: Variable[] = [
      { name: "tenant" },
      { name: "password", secret: true },
      { name: "region" },
    ];

    expect(runAgainValues(declared, { tenant: "acme", region: "eu" })).toEqual([
      { name: "tenant", secret: false, value: "acme" },
      { name: "password", secret: true, value: "" },
      { name: "region", secret: false, value: "eu" },
    ]);
  });
});

describe("step rail badges", () => {
  it("badges drift, completed-by-you, selector failure, skipped, and counts", () => {
    expect(
      stepRailBadges(
        result({
          step_id: "s2",
          matched_candidate_rank: 2,
          candidate_count: 5,
        }),
      ).map((badge) => badge.label),
    ).toContain("found on candidate 3/5");

    expect(
      stepRailBadges(
        result({
          step_id: "s5",
          completed_by_human: true,
        }),
      ).map((badge) => badge.label),
    ).toContain("completed by you · verified ✓");

    expect(
      stepRailBadges(
        result({
          step_id: "s6",
          status: "failed",
          error_code: "no_candidate_resolved",
          matched_candidate_rank: null,
        }),
      ).map((badge) => badge.label),
    ).toContain("selector failure");

    expect(
      stepRailBadges(result({ step_id: "s7", status: "skipped" })).map((b) => b.label),
    ).toContain("skipped");

    expect(
      stepRailBadges(
        result({
          step_id: "s8",
          extracted_value: [{ a: 1 }, { a: 2 }],
        }),
        [{ id: "d1", step_id: "s8", kind: "download" } as ArtifactRecord],
      ).map((badge) => badge.label),
    ).toEqual(expect.arrayContaining(["2 records", "1 file"]));
  });
});

describe("meta and pane placeholders", () => {
  it("sums time with you from waiting, human, and verifying, never automation", () => {
    const intervals: ControlIntervalRecord[] = [
      { id: "i1", kind: "automation", started_at: T(0), ended_at: T(10) },
      { id: "i2", kind: "waiting", started_at: T(10), ended_at: T(16) },
      { id: "i3", kind: "human", started_at: T(16), ended_at: T(27) },
      { id: "i4", kind: "verifying", started_at: T(27), ended_at: T(29) },
    ];
    expect(timeWithYouMs(intervals, new Date(T(29)))).toBe(19_000);
    expect(elapsedMs(run({ started_at: T(0), ended_at: T(39) }), new Date(T(100)))).toBe(39_000);
  });

  it("holds a placeholder in the pane until the VNC slice arrives", () => {
    expect(panePlaceholder("running", false)).toBe("view only — automation in control");
    expect(panePlaceholder("waiting_for_human", false)).toBe(
      "waiting for you — the browser is held",
    );
    expect(panePlaceholder("succeeded", false)).toBe("session ended — the browser closed");
    expect(panePlaceholder("running", true)).toBe("cancelling — waiting for a Step boundary");
  });
});

describe("the Output tab", () => {
  const invoices = [
    { number: "INV-0000", client: "Client 0", amount: "0.00", status: "open" },
    { number: "INV-0001", client: "Client 1", amount: "1.00", status: "open" },
  ];

  it("turns a list of records into a table, and an empty assembly into a sentence", () => {
    expect(outputTable(invoices)).toEqual({
      columns: ["number", "client", "amount", "status"],
      rows: [
        ["INV-0000", "Client 0", "0.00", "open"],
        ["INV-0001", "Client 1", "1.00", "open"],
      ],
    });
    expect(outputTable({ invoices, total: "48.00" })).toEqual({
      columns: ["invoices", "total"],
      rows: [[JSON.stringify(invoices), "48.00"]],
    });
    expect(outputTable({})).toBeNull();
    expect(outputTable([])).toBeNull();
    expect(EMPTY_OUTPUT).toBe("This Run extracted no data.");
  });

  it("points both download buttons at the endpoint's formats", () => {
    expect(outputDownloadHref("run-1", "json")).toBe("/api/runs/run-1/output?format=json");
    expect(outputDownloadHref("run-1", "csv")).toBe("/api/runs/run-1/output?format=csv");
  });
});
