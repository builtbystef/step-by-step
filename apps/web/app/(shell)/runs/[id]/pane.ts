import type {
  AuthStateCandidateRecord,
  AuthStateConsentScope,
  ControlIntervalRecord,
  RunControlKind,
  RunStatus,
  RunTrigger,
  StepResultRecord,
} from "@step-by-step/api-client";

import type { Step } from "../../workflows/[id]/editor/steps";

import { clock, isTerminal } from "./presentation";

export const LOW_COUNTDOWN_MS = 5 * 60 * 1000;

export type PaneFrame = "none" | "view_only" | "interactive" | "ended";
export type PaneHighlight = "none" | "wait" | "human";

export type PaneInput = {
  status: RunStatus;
  cancelling: boolean;
  phase: RunControlKind | null;
  weHoldControl: boolean;
  heldElsewhere: boolean;
  unmetHandback: boolean;
  workerId?: string | null;
};

export type PaneView = {
  frame: PaneFrame;
  highlight: PaneHighlight;
  caption: string | null;
  identity: string | null;
  showWaitingCard: boolean;
  showControlBar: boolean;
  showUnmetChoice: boolean;
  showHeldNote: boolean;
  heldNote: string | null;
  unmetKeep: string;
  unmetGiveUp: string;
};

const UNMET_KEEP = "keep control and finish it";
const UNMET_GIVE_UP = "give up: fail the run";
const HELD_NOTE = "Control is held in another tab.";

export function paneView(input: PaneInput): PaneView {
  const { status, cancelling, phase, weHoldControl, heldElsewhere, unmetHandback, workerId } =
    input;
  const base: PaneView = {
    frame: "none",
    highlight: "none",
    caption: null,
    identity: null,
    showWaitingCard: false,
    showControlBar: false,
    showUnmetChoice: false,
    showHeldNote: false,
    heldNote: null,
    unmetKeep: UNMET_KEEP,
    unmetGiveUp: UNMET_GIVE_UP,
  };

  if (cancelling && !isTerminal(status)) {
    return { ...base, caption: "cancelling: waiting for a Step boundary" };
  }
  if (isTerminal(status)) {
    return { ...base, frame: "ended", caption: "session ended: the browser closed" };
  }
  if (status === "queued") {
    return { ...base, caption: "queued: waiting for a Worker" };
  }

  if (status === "waiting_for_human" && unmetHandback) {
    return {
      ...base,
      frame: "view_only",
      highlight: "wait",
      showUnmetChoice: true,
    };
  }

  if (status === "waiting_for_human" && weHoldControl) {
    const who = workerId ? ` · ${workerId}` : "";
    return {
      ...base,
      frame: "interactive",
      highlight: "human",
      showControlBar: true,
      identity: `You are controlling this browser${who}`,
    };
  }

  if (status === "waiting_for_human" && heldElsewhere) {
    return {
      ...base,
      frame: "view_only",
      highlight: "human",
      showHeldNote: true,
      heldNote: HELD_NOTE,
    };
  }

  if (status === "waiting_for_human") {
    return {
      ...base,
      frame: "view_only",
      highlight: "wait",
      showWaitingCard: phase !== "verifying",
    };
  }

  return {
    ...base,
    frame: "view_only",
    caption: "view only: automation in control",
  };
}

export function waitingStep(
  steps: Step[],
  results: StepResultRecord[],
  inFlight: { stepId: string } | null,
): Extract<Step, { type: "pause-for-takeover" }> | null {
  if (inFlight !== null) {
    const flying = steps.find((step) => step.id === inFlight.stepId);
    return flying?.type === "pause-for-takeover" ? flying : null;
  }
  const done = new Set(results.map((result) => result.step_id));
  const next = steps.find((step) => !done.has(step.id) && step.type === "pause-for-takeover");
  return next?.type === "pause-for-takeover" ? next : null;
}

export function waitingReason(
  pause: Extract<Step, { type: "pause-for-takeover" }> | null,
  pauseRequested: boolean,
): string {
  const message = pause?.payload.message;
  if (typeof message === "string" && message.length > 0) {
    return message;
  }
  if (pauseRequested) {
    return "A pause was requested.";
  }
  return "This Run is waiting for you.";
}

export type CountdownState = {
  remainingMs: number;
  label: string;
  low: boolean;
};

export function countdownState(deadlineAt: string | null, now: Date): CountdownState | null {
  if (deadlineAt === null) {
    return null;
  }
  const remainingMs = Math.max(0, Date.parse(deadlineAt) - now.getTime());
  return {
    remainingMs,
    label: `${clock(remainingMs)} left`,
    low: remainingMs <= LOW_COUNTDOWN_MS,
  };
}

export type PredicateLine = {
  state: "met" | "unmet" | "none";
  grace: string | null;
  offerStay: boolean;
  offerHandBackNow: boolean;
};

export function predicateLine(input: {
  hasCheck: boolean;
  met: boolean | null;
  graceEndsAt: string | null;
  autoHandbackDisabled: boolean;
  now: Date;
  controlling: boolean;
}): PredicateLine {
  if (!input.hasCheck) {
    return { state: "none", grace: null, offerStay: false, offerHandBackNow: false };
  }
  const met = input.met === true;
  const graceOpen =
    met && input.controlling && !input.autoHandbackDisabled && input.graceEndsAt !== null;
  const remaining = graceOpen
    ? Math.max(0, Math.ceil((Date.parse(input.graceEndsAt ?? "") - input.now.getTime()) / 1000))
    : 0;
  return {
    state: met ? "met" : "unmet",
    grace: graceOpen ? `handing back in ${String(remaining)}s` : null,
    offerStay: graceOpen,
    offerHandBackNow: graceOpen || (met && input.controlling),
  };
}

export function challengeBanner(diagnostic: {
  stepId: string;
  kind: string;
  detail: string;
  at: string;
}): { title: string; action: string } | null {
  if (diagnostic.kind !== "suspected_challenge") {
    return null;
  }
  return {
    title: "This step may be blocked by a challenge.",
    action: "pause run & take over",
  };
}

export type ConsentPrompt = {
  domain: string;
  question: string;
  scopes: AuthStateConsentScope[];
};

export function consentPrompts(
  candidates: AuthStateCandidateRecord[],
  trigger: RunTrigger,
): ConsentPrompt[] {
  const personal = trigger === "manual" || trigger === "test";
  return candidates
    .filter((candidate) => candidate.consent === null)
    .map((candidate) => ({
      domain: candidate.domain,
      question: `Keep this login for ${candidate.domain}?`,
      scopes: personal ? ["organization", "personal"] : ["organization"],
    }));
}

export type TakeoverLock = {
  tabId: string;
  at: string;
};

export function heldElsewhere(lock: TakeoverLock | null, tabId: string): boolean {
  return lock !== null && lock.tabId !== tabId;
}

export function currentPhase(intervals: ControlIntervalRecord[]): RunControlKind | null {
  const open = [...intervals].reverse().find((interval) => interval.ended_at === null);
  return (open ?? intervals[intervals.length - 1])?.kind ?? null;
}

export function vncSocketUrl(wsPath: string, location: { protocol: string; host: string }): string {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${location.host}${wsPath}`;
}
