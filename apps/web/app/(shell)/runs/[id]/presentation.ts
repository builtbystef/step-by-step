import type {
  ArtifactRecord,
  ControlIntervalRecord,
  LogLine,
  RunControlKind,
  RunRecord,
  RunStatus,
  StepResultRecord,
  Variable,
} from "@step-by-step/api-client";

import type { AttributeTone } from "@/components/primitives/attribute-badge";
import type { LifecycleState } from "@/lib/labels";

import { targetsOf, type Step } from "../../workflows/[id]/editor/steps";

/**
 * The cockpit's wording and arithmetic, kept out of the JSX so a test can
 * read the acceptance criteria back: the clock, the drift chip, the timeline
 * proportions, the terminal sentences, cancel, and Run again's prefill.
 *
 * Lifecycle state is named here only as a value handed to `StatusChip`.
 * This module never words a state itself.
 */

const TERMINAL: ReadonlySet<RunStatus> = new Set(["succeeded", "failed", "cancelled"]);

/** Elapsed as the banner writes it: unpadded minutes, two-digit seconds. */
export function clock(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${String(minutes)}:${String(seconds).padStart(2, "0")}`;
}

export function chipState(run: Pick<RunRecord, "status" | "cancel_requested_at">): LifecycleState {
  if (TERMINAL.has(run.status)) {
    return run.status;
  }
  if (run.cancel_requested_at !== null) {
    return "cancelling";
  }
  return run.status;
}

export function isTerminal(status: RunStatus): boolean {
  return TERMINAL.has(status);
}

/** Selector Drift: any match that was not the recorded best candidate. */
export function driftedCount(results: StepResultRecord[]): number {
  return results.filter((result) => isDrifted(result.matched_candidate_rank)).length;
}

export function isDrifted(rank: number | null): boolean {
  return rank !== null && rank > 0;
}

export function driftChipLabel(count: number): string | null {
  if (count <= 0) {
    return null;
  }
  return count === 1 ? "⚠ 1 step drifted" : `⚠ ${String(count)} steps drifted`;
}

export function driftBadgeLabel(rank: number, count: number): string {
  return `found on candidate ${String(rank + 1)}/${String(count)}`;
}

export type CandidateFate = "died" | "matched" | "untried";

export function candidateFates(
  candidateCount: number,
  matchedRank: number | null,
): CandidateFate[] {
  return Array.from({ length: candidateCount }, (_, rank) => {
    if (matchedRank === null) {
      return "died";
    }
    if (rank < matchedRank) {
      return "died";
    }
    if (rank === matchedRank) {
      return "matched";
    }
    return "untried";
  });
}

export function repickHref(workflowId: string, stepId: string): string {
  return `/workflows/${workflowId}/editor?repick=${stepId}`;
}

export type BannerInput = {
  run: RunRecord;
  results: StepResultRecord[];
  artifacts: ArtifactRecord[];
  totalSteps: number;
};

export function recordCount(results: StepResultRecord[]): number {
  let total = 0;
  for (const result of results) {
    total += extractedCount(result.extracted_value);
  }
  return total;
}

export function extractedCount(value: unknown): number {
  if (value === null || value === undefined) {
    return 0;
  }
  return Array.isArray(value) ? value.length : 1;
}

export function downloadCount(artifacts: ArtifactRecord[]): number {
  return artifacts.filter((artifact) => artifact.kind === "download").length;
}

export function terminalBanner(input: BannerInput): string | null {
  const { run, results, artifacts, totalSteps } = input;
  if (run.status === "succeeded") {
    const elapsed = elapsedMs(run, new Date(run.ended_at ?? run.started_at ?? run.queued_at));
    const passed = results.filter((result) => result.status === "passed").length;
    const records = recordCount(results);
    const files = downloadCount(artifacts);
    return (
      `succeeded in ${clock(elapsed)} · ${String(passed)} of ${String(totalSteps)} steps` +
      ` · ${String(records)} records · ${String(files)} download${files === 1 ? "" : "s"}`
    );
  }
  if (run.status === "failed") {
    const failed = results.find((result) => result.status === "failed");
    const skipped = results.filter((result) => result.status === "skipped").length;
    const stepNo = failed === undefined ? "?" : String(failed.position + 1);
    const reason = run.failure_reason ?? "failed";
    return `failed at step ${stepNo} · ${reason} · remaining ${String(skipped)} steps skipped`;
  }
  if (run.status === "cancelled") {
    const elapsed = elapsedMs(run, new Date(run.ended_at ?? run.queued_at));
    const kept = results.filter((result) => result.status !== "skipped").length;
    return `cancelled in ${clock(elapsed)} · ${String(kept)} of ${String(totalSteps)} steps`;
  }
  return null;
}

export function offersRepick(run: RunRecord, results: StepResultRecord[]): boolean {
  return (
    run.status === "failed" &&
    run.failure_reason === "step_failed" &&
    results.some(hasTargetFailure)
  );
}

function hasTargetFailure(result: StepResultRecord): boolean {
  return result.status === "failed" && result.error_code === "no_candidate_resolved";
}

export const CANCEL_CONFIRM =
  "The Worker finishes the action it is on, then stops at the next Step boundary — it never stops mid-click.";

export function cancellingBand(stepNumber: number): string {
  return `cancelling — waiting for step ${String(stepNumber)} to reach a boundary`;
}

export type PrefillVariable = {
  name: string;
  secret: boolean;
  value: string;
};

export function runAgainValues(
  declared: Variable[],
  stored: Record<string, unknown>,
): PrefillVariable[] {
  return declared.map((variable) => {
    const secret = variable.secret === true;
    const raw = stored[variable.name];
    return {
      name: variable.name,
      secret,
      value: secret ? "" : scalarValue(raw),
    };
  });
}

function scalarValue(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (value === undefined || value === null) {
    return "";
  }
  return JSON.stringify(value);
}

export type TimelineSegment = {
  kind: RunControlKind;
  flex: number;
  durationMs: number;
};

export type TimelineMarker = {
  label: "paused" | "you took control" | "handed back" | "resumed";
  at: number;
};

export function timeline(
  intervals: ControlIntervalRecord[],
  now: Date,
): { segments: TimelineSegment[]; markers: TimelineMarker[] } {
  const durations = intervals.map((interval) => intervalMs(interval, now));
  const total = durations.reduce((sum, ms) => sum + ms, 0);
  const segments: TimelineSegment[] = intervals.map((interval, index) => ({
    kind: interval.kind,
    durationMs: durations[index] ?? 0,
    flex: total === 0 ? 1 / Math.max(intervals.length, 1) : (durations[index] ?? 0) / total,
  }));

  const markers: TimelineMarker[] = [];
  let elapsed = 0;
  for (let index = 0; index < intervals.length; index += 1) {
    const interval = intervals[index];
    if (interval !== undefined && index > 0) {
      const label = markerFor(interval.kind);
      if (label !== null) {
        markers.push({ label, at: total === 0 ? 0 : elapsed / total });
      }
    }
    elapsed += durations[index] ?? 0;
  }
  return { segments, markers };
}

function markerFor(kind: RunControlKind): TimelineMarker["label"] | null {
  if (kind === "waiting") {
    return "paused";
  }
  if (kind === "human") {
    return "you took control";
  }
  if (kind === "verifying") {
    return "handed back";
  }
  return "resumed";
}

function intervalMs(interval: ControlIntervalRecord, now: Date): number {
  const start = Date.parse(interval.started_at);
  const end = interval.ended_at === null ? now.getTime() : Date.parse(interval.ended_at);
  return Math.max(0, end - start);
}

export function timeWithYouMs(intervals: ControlIntervalRecord[], now: Date): number {
  return intervals
    .filter((interval) => interval.kind !== "automation")
    .reduce((sum, interval) => sum + intervalMs(interval, now), 0);
}

export function elapsedMs(run: RunRecord, now: Date): number {
  const start = run.started_at ?? run.queued_at;
  const end = run.ended_at ?? now.toISOString();
  return Math.max(0, Date.parse(end) - Date.parse(start));
}

export function stepsDoneLabel(results: StepResultRecord[], totalSteps: number): string {
  const done = results.filter(
    (result) => result.status === "passed" || result.status === "failed",
  ).length;
  return `${String(done)} / ${String(totalSteps)}`;
}

export type StepRailBadge = {
  key: string;
  label: string;
  tone: AttributeTone;
};

export function stepRailBadges(
  result: StepResultRecord,
  artifacts: ArtifactRecord[] = [],
): StepRailBadge[] {
  const badges: StepRailBadge[] = [];
  if (
    result.matched_candidate_rank !== null &&
    result.candidate_count !== null &&
    isDrifted(result.matched_candidate_rank)
  ) {
    badges.push({
      key: "drift",
      label: driftBadgeLabel(result.matched_candidate_rank, result.candidate_count),
      tone: "wait",
    });
  }
  if (result.completed_by_human) {
    badges.push({
      key: "human",
      label: "completed by you · verified ✓",
      tone: "human",
    });
  }
  if (result.status === "failed" && result.error_code === "no_candidate_resolved") {
    badges.push({ key: "selector", label: "selector failure", tone: "bad" });
  }
  if (result.status === "skipped") {
    badges.push({ key: "skipped", label: "skipped", tone: "neutral" });
  }
  const records = extractedCount(result.extracted_value);
  if (records > 0) {
    badges.push({
      key: "records",
      label: `${String(records)} record${records === 1 ? "" : "s"}`,
      tone: "neutral",
    });
  }
  const files = artifacts.filter(
    (artifact) => artifact.step_id === result.step_id && artifact.kind === "download",
  ).length;
  if (files > 0) {
    badges.push({
      key: "files",
      label: `${String(files)} file${files === 1 ? "" : "s"}`,
      tone: "neutral",
    });
  }
  return badges;
}

export type StepExpansion = {
  error: { code: string; message: string } | null;
  candidates: { kind: string; value: string; fate: CandidateFate }[];
  screenshots: ArtifactRecord[];
  extracted: unknown;
  logs: LogLine[];
  repickHref: string | null;
};

export function stepExpansion(input: {
  workflowId: string;
  step: Step;
  result: StepResultRecord | null;
  artifacts: ArtifactRecord[];
  logs: LogLine[];
}): StepExpansion {
  const { workflowId, step, result, artifacts, logs } = input;
  const [target] = targetsOf(step);
  const count = result?.candidate_count ?? target?.candidates.length ?? 0;
  const fates = candidateFates(count, result?.matched_candidate_rank ?? null);
  const candidates = (target?.candidates ?? []).map((candidate, index) => ({
    kind: candidate.kind,
    value: candidate.value,
    fate: fates[index] ?? "untried",
  }));
  const failed = result?.status === "failed";
  return {
    error:
      failed && result.error_code !== null
        ? { code: result.error_code, message: result.error_message ?? "" }
        : null,
    candidates,
    screenshots: artifacts.filter(
      (artifact) => artifact.step_id === step.id && artifact.kind === "screenshot",
    ),
    extracted: result?.extracted_value ?? null,
    logs: logs.filter((line) => line.step_id === step.id),
    repickHref: target === undefined ? null : repickHref(workflowId, step.id),
  };
}

export type RailItem =
  | {
      kind: "step";
      position: number;
      step: Step;
      result: StepResultRecord | null;
      inFlight: boolean;
      durationMs: number | null;
      badges: StepRailBadge[];
    }
  | {
      kind: "control";
      phase: Exclude<RunControlKind, "automation">;
      durationMs: number;
      label: string;
    };

export function railItems(input: {
  steps: Step[];
  results: StepResultRecord[];
  artifacts: ArtifactRecord[];
  intervals: ControlIntervalRecord[];
  inFlight: { stepId: string; position: number; startedAt: string } | null;
  now: Date;
}): RailItem[] {
  const { steps, results, artifacts, intervals, inFlight, now } = input;
  const byId = new Map(results.map((result) => [result.step_id, result]));
  const items: RailItem[] = [];

  for (const [index, step] of steps.entries()) {
    for (const band of controlBandsBefore(intervals, steps, byId, index, now)) {
      items.push(band);
    }
    if (step === undefined) {
      continue;
    }
    const result = byId.get(step.id) ?? null;
    const flying = inFlight?.stepId === step.id;
    items.push({
      kind: "step",
      position: index,
      step,
      result,
      inFlight: flying,
      durationMs: stepDurationMs(result, flying ? inFlight : null, now),
      badges: result === null ? [] : stepRailBadges(result, artifacts),
    });
  }
  for (const band of controlBandsBefore(intervals, steps, byId, steps.length, now)) {
    items.push(band);
  }
  return items;
}

function stepDurationMs(
  result: StepResultRecord | null,
  inFlight: { startedAt: string } | null,
  now: Date,
): number | null {
  if (result?.started_at !== null && result?.started_at !== undefined && result.ended_at) {
    return Math.max(0, Date.parse(result.ended_at) - Date.parse(result.started_at));
  }
  if (inFlight !== null) {
    return Math.max(0, now.getTime() - Date.parse(inFlight.startedAt));
  }
  return null;
}

function controlBandsBefore(
  intervals: ControlIntervalRecord[],
  steps: Step[],
  results: Map<string, StepResultRecord>,
  index: number,
  now: Date,
): Extract<RailItem, { kind: "control" }>[] {
  const bands: Extract<RailItem, { kind: "control" }>[] = [];
  for (const interval of intervals) {
    if (interval.kind === "automation") {
      continue;
    }
    if (bandIndex(interval, steps, results) !== index) {
      continue;
    }
    const durationMs = intervalMs(interval, now);
    bands.push({
      kind: "control",
      phase: interval.kind,
      durationMs,
      label: controlBandLabel(interval.kind, durationMs, interval.ended_at !== null),
    });
  }
  return bands;
}

/**
 * A non-automation interval sits before the first Step that started after it,
 * or after every started Step when none did.
 */
function bandIndex(
  interval: ControlIntervalRecord,
  steps: Step[],
  results: Map<string, StepResultRecord>,
): number {
  const start = Date.parse(interval.started_at);
  for (const [index, step] of steps.entries()) {
    const result = step === undefined ? undefined : results.get(step.id);
    const started = result?.started_at;
    if (started !== null && started !== undefined && Date.parse(started) > start) {
      return index;
    }
  }
  return steps.length;
}

export function controlBandLabel(
  kind: Exclude<RunControlKind, "automation">,
  durationMs: number,
  closed: boolean,
): string {
  const time = clock(durationMs);
  if (kind === "waiting") {
    return `waiting for you — ${time}`;
  }
  if (kind === "human") {
    return `you were in control — ${time}`;
  }
  return closed
    ? `verifying the success check — ${time} · passed, automation resumed`
    : `verifying the success check — ${time}`;
}

export function panePlaceholder(status: RunStatus, cancelling: boolean): string {
  if (cancelling && !TERMINAL.has(status)) {
    return "cancelling — waiting for a Step boundary";
  }
  if (status === "queued") {
    return "queued — waiting for a Worker";
  }
  if (status === "waiting_for_human") {
    return "waiting for you — the browser is held";
  }
  if (TERMINAL.has(status)) {
    return "session ended — the browser closed";
  }
  return "view only — automation in control";
}

export function triggerLabel(trigger: RunRecord["trigger"]): string {
  if (trigger === "test") {
    return "test";
  }
  if (trigger === "schedule") {
    return "schedule";
  }
  if (trigger === "batch") {
    return "batch";
  }
  return "manual";
}

export function versionLabel(run: RunRecord): string {
  if (run.is_test || run.version_number === null) {
    return "test";
  }
  return `v${String(run.version_number)}`;
}

export function currentStepNumber(
  inFlight: { position: number } | null,
  results: StepResultRecord[],
): number {
  if (inFlight !== null) {
    return inFlight.position + 1;
  }
  const last = results.reduce<StepResultRecord | null>(
    (found, result) => (found === null || result.position > found.position ? result : found),
    null,
  );
  return (last?.position ?? 0) + 1;
}
