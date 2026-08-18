/**
 * The single source of every state's wording.
 *
 * No screen phrases a status itself: a lifecycle state reaches the user only
 * through `lifecycleLabel`, and only inside a `StatusChip`. Changing a word
 * here changes it everywhere, which is the point.
 */

/** Every lifecycle state a Run, an Occurrence, or a Batch row can be in. */
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

/** A hue of the semantic ramp. One hue, one meaning. */
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

// Grey is the resting colour: nothing here is asking anything of anyone.
// `skipped` is grey with the rest — amber means "a human is needed", and no
// skip needs one.
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

/** The states still in motion, which is what earns a chip its leading dot. */
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

/**
 * The extension's connection states. "not installed" and "installed but not
 * pointed at this instance" are indistinguishable from the app's side, so they
 * are deliberately one state with one recovery path.
 */
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
