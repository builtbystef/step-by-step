import type {
  AuthStateCandidateRecord,
  ControlIntervalRecord,
  RunRecord,
  StepResultRecord,
} from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import type { Step } from "../../workflows/[id]/editor/steps";

import {
  challengeBanner,
  consentPrompts,
  countdownState,
  currentPhase,
  heldElsewhere,
  paneView,
  predicateLine,
  vncSocketUrl,
  waitingReason,
  waitingStep,
} from "./pane";
import { clock, terminalBanner } from "./presentation";

const START = "2026-08-26T12:00:00.000Z";
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
    worker_id: "worker-2",
    worker_vnc_endpoint: "worker-2:5900",
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

function pauseStep(
  message: string,
  withCheck = true,
): Extract<Step, { type: "pause-for-takeover" }> {
  return {
    id: "s5",
    label: "Complete MFA if asked",
    type: "pause-for-takeover",
    payload: {
      message,
      successCheck: withCheck ? { candidates: [{ kind: "role", value: "Dashboard" }] } : null,
    },
  };
}

describe("the pane's three states", () => {
  it("is view-only while automation runs, and says so", () => {
    const view = paneView({
      status: "running",
      cancelling: false,
      phase: "automation",
      weHoldControl: false,
      heldElsewhere: false,
      unmetHandback: false,
    });
    expect(view.frame).toBe("view_only");
    expect(view.highlight).toBe("none");
    expect(view.caption).toBe("view only: automation in control");
    expect(view.showWaitingCard).toBe(false);
    expect(view.showControlBar).toBe(false);
  });

  it("turns amber and opens the waiting card when the Run parks", () => {
    const view = paneView({
      status: "waiting_for_human",
      cancelling: false,
      phase: "waiting",
      weHoldControl: false,
      heldElsewhere: false,
      unmetHandback: false,
    });
    expect(view.frame).toBe("view_only");
    expect(view.highlight).toBe("wait");
    expect(view.showWaitingCard).toBe(true);
    expect(view.showControlBar).toBe(false);
  });

  it("becomes interactive with the control bar once this tab takes over", () => {
    const view = paneView({
      status: "waiting_for_human",
      cancelling: false,
      phase: "waiting",
      weHoldControl: true,
      heldElsewhere: false,
      unmetHandback: false,
      workerId: "worker-2",
    });
    expect(view.frame).toBe("interactive");
    expect(view.highlight).toBe("human");
    expect(view.showControlBar).toBe(true);
    expect(view.showWaitingCard).toBe(false);
    expect(view.identity).toBe("You are controlling this browser · worker-2");
  });

  it("stays view-only with the where-is-control note in a second tab", () => {
    const view = paneView({
      status: "waiting_for_human",
      cancelling: false,
      phase: "human",
      weHoldControl: false,
      heldElsewhere: true,
      unmetHandback: false,
    });
    expect(view.frame).toBe("view_only");
    expect(view.showHeldNote).toBe(true);
    expect(view.heldNote).toBe("Control is held in another tab.");
    expect(view.showControlBar).toBe(false);
    expect(view.showWaitingCard).toBe(false);
  });

  it("reports the session ended on a terminal Run, including a timed-out takeover", () => {
    const view = paneView({
      status: "failed",
      cancelling: false,
      phase: null,
      weHoldControl: false,
      heldElsewhere: false,
      unmetHandback: false,
    });
    expect(view.frame).toBe("ended");
    expect(view.caption).toBe("session ended: the browser closed");
    expect(
      terminalBanner({
        run: run({
          status: "failed",
          failure_reason: "takeover_timeout",
          ended_at: T(30),
        }),
        results: [],
        artifacts: [],
        totalSteps: 8,
      }),
    ).toContain("takeover_timeout");
  });
});

describe("the waiting card", () => {
  it("shows the pause Step's author-written message, or the pause request", () => {
    const steps: Step[] = [
      { id: "s1", label: "Go", type: "navigate", payload: { url: "https://x" } },
      pauseStep("Complete MFA if asked"),
    ];
    expect(waitingStep(steps, [], null)?.id).toBe("s5");
    expect(waitingReason(pauseStep("Complete MFA if asked"), false)).toBe("Complete MFA if asked");
    expect(waitingReason(null, true)).toBe("A pause was requested.");
  });

  it("ticks the deadline and turns the countdown red when five minutes remain", () => {
    const plenty = countdownState(T(20 * 60), new Date(T(0)));
    expect(plenty?.label).toBe(`${clock(20 * 60 * 1000)} left`);
    expect(plenty?.low).toBe(false);

    const low = countdownState(T(4 * 60), new Date(T(0)));
    expect(low?.low).toBe(true);
    expect(low?.label).toBe(`${clock(4 * 60 * 1000)} left`);
  });
});

describe("the success-check line", () => {
  it("flips met and unmet with the page, and shows the grace while auto hand-back is on", () => {
    expect(
      predicateLine({
        hasCheck: true,
        met: false,
        graceEndsAt: null,
        autoHandbackDisabled: false,
        now: new Date(T(0)),
        controlling: true,
      }),
    ).toMatchObject({ state: "unmet", grace: null });

    const met = predicateLine({
      hasCheck: true,
      met: true,
      graceEndsAt: T(6),
      autoHandbackDisabled: false,
      now: new Date(T(2)),
      controlling: true,
    });
    expect(met.state).toBe("met");
    expect(met.grace).toBe("handing back in 4s");
    expect(met.offerStay).toBe(true);
    expect(met.offerHandBackNow).toBe(true);

    const held = predicateLine({
      hasCheck: true,
      met: true,
      graceEndsAt: T(6),
      autoHandbackDisabled: true,
      now: new Date(T(3)),
      controlling: true,
    });
    expect(held.grace).toBeNull();
    expect(held.offerStay).toBe(false);
    expect(held.state).toBe("met");
  });
});

describe("the unmet hand-back choice", () => {
  it("offers keep-control or give-up after a hand-back the check did not pass", () => {
    const view = paneView({
      status: "waiting_for_human",
      cancelling: false,
      phase: "waiting",
      weHoldControl: false,
      heldElsewhere: false,
      unmetHandback: true,
    });
    expect(view.showUnmetChoice).toBe(true);
    expect(view.showWaitingCard).toBe(false);
    expect(view.unmetKeep).toBe("keep control and finish it");
    expect(view.unmetGiveUp).toBe("give up: fail the run");
  });
});

describe("the challenge banner and consent prompt", () => {
  it("worded a suspected_challenge as a dismissible pause offer", () => {
    expect(
      challengeBanner({ stepId: "s3", kind: "suspected_challenge", detail: "", at: T(10) }),
    ).toEqual({
      title: "This step may be blocked by a challenge.",
      action: "pause run & take over",
    });
  });

  it("asks to keep a new-domain login, organization-only on a Schedule", () => {
    const candidates: AuthStateCandidateRecord[] = [
      { domain: "site.com", consent: null },
      { domain: "kept.example", consent: { scope: "organization" } },
    ];
    expect(consentPrompts(candidates, "manual").map((prompt) => prompt.domain)).toEqual([
      "site.com",
    ]);
    expect(consentPrompts(candidates, "manual")[0]).toMatchObject({
      question: "Keep this login for site.com?",
      scopes: ["organization", "personal"],
    });
    expect(consentPrompts(candidates, "schedule")[0]?.scopes).toEqual(["organization"]);
  });
});

describe("held-elsewhere and the open interval", () => {
  it("treats another tab's lock as held elsewhere, and the open interval as the phase", () => {
    expect(heldElsewhere({ tabId: "tab-a", at: T(1) }, "tab-b")).toBe(true);
    expect(heldElsewhere({ tabId: "tab-a", at: T(1) }, "tab-a")).toBe(false);
    expect(heldElsewhere(null, "tab-b")).toBe(false);

    const intervals: ControlIntervalRecord[] = [
      { id: "i1", kind: "automation", started_at: T(0), ended_at: T(10) },
      { id: "i2", kind: "waiting", started_at: T(10), ended_at: null },
    ];
    expect(currentPhase(intervals)).toBe("waiting");
  });
});

describe("the VNC socket URL", () => {
  it("turns the ticket path into a same-origin WebSocket URL", () => {
    expect(
      vncSocketUrl("/api/runs/run-1/vnc?ticket=abc", {
        protocol: "https:",
        host: "app.example",
      }),
    ).toBe("wss://app.example/api/runs/run-1/vnc?ticket=abc");
  });
});

describe("give-up lands on the abandoned failure reason", () => {
  it("is the wording the terminal banner already uses", () => {
    expect(
      terminalBanner({
        run: run({
          status: "failed",
          failure_reason: "takeover_abandoned",
          ended_at: T(20),
        }),
        results: [{ status: "failed", position: 4 } as StepResultRecord],
        artifacts: [],
        totalSteps: 8,
      }),
    ).toContain("takeover_abandoned");
  });
});
