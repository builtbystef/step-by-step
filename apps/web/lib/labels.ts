export const LIFECYCLE_STATES = [
  "queued",
  "running",
  "waiting_for_human",
  "succeeded",
  "failed",
  "cancelling",
  "cancelled",
  "skipped",
  "missed",
  "paused",
] as const;

export type LifecycleState = (typeof LIFECYCLE_STATES)[number];

export type LifecycleTone = "neutral" | "accent" | "wait" | "ok" | "bad";

const LIFECYCLE_LABELS: Record<LifecycleState, string> = {
  queued: "queued",
  running: "running",
  waiting_for_human: "needs you",
  succeeded: "succeeded",
  failed: "failed",
  cancelling: "cancelling",
  cancelled: "cancelled",
  skipped: "skipped",
  missed: "missed",
  paused: "paused",
};

const LIFECYCLE_TONES: Record<LifecycleState, LifecycleTone> = {
  queued: "neutral",
  running: "accent",
  waiting_for_human: "wait",
  succeeded: "ok",
  failed: "bad",
  cancelling: "neutral",
  cancelled: "neutral",
  skipped: "neutral",
  missed: "neutral",
  paused: "neutral",
};

const LIVE_STATES: ReadonlySet<LifecycleState> = new Set<LifecycleState>([
  "running",
  "waiting_for_human",
]);

export function lifecycleLabel(state: LifecycleState): string {
  return LIFECYCLE_LABELS[state];
}

export function lifecycleTone(state: LifecycleState): LifecycleTone {
  return LIFECYCLE_TONES[state];
}

export function isLiveState(state: LifecycleState): boolean {
  return LIVE_STATES.has(state);
}

export const CONNECTION_STATES = ["connected", "not_connected", "out_of_date"] as const;

export type ConnectionState = (typeof CONNECTION_STATES)[number];

const CONNECTION_LABELS: Record<ConnectionState, string> = {
  connected: "connected",
  not_connected: "not connected",
  out_of_date: "out of date",
};

export function connectionLabel(state: ConnectionState): string {
  return CONNECTION_LABELS[state];
}
