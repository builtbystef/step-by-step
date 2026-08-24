import type { CountTone } from "@/components/primitives/count-badge";

export const ATTENTION_KEY = ["attention"] as const;
export const RUNS_KEY = ["/api/runs"] as const;

const POLL_MS = 10_000;

export type AttentionCounts = {
  waiting_count: number;
  running_count: number;
  queued_count: number;
};

export function attentionMessage(waitingCount: number, runLabel: string): string {
  return waitingCount === 1
    ? `${runLabel} is waiting for you`
    : `${String(waitingCount)} Runs are waiting for you — the soonest is ${runLabel}`;
}

export function formatDeadline(deadline: string, now = Date.now()): string {
  const remainingSeconds = Math.ceil((Date.parse(deadline) - now) / 1000);
  if (remainingSeconds <= 0) return "the deadline has passed";

  const hours = Math.floor(remainingSeconds / 3600);
  const minutes = Math.floor((remainingSeconds % 3600) / 60);
  const seconds = remainingSeconds % 60;
  return [hours, minutes, seconds].map((part) => String(part).padStart(2, "0")).join(":");
}

export function attentionRefetchInterval(visibility: DocumentVisibilityState): number | false {
  return visibility === "visible" ? POLL_MS : false;
}

export function runsBadge(counts: AttentionCounts): { count: number; tone: CountTone } {
  return {
    count: counts.waiting_count + counts.running_count + counts.queued_count,
    tone: counts.waiting_count > 0 ? "waiting" : "in-flight",
  };
}

type InvalidatingCache = {
  invalidateQueries: (filters: { queryKey: readonly string[] }) => Promise<unknown>;
};

/** Start, cancel, hand-back, and stream transitions all call this one rule. */
export async function invalidateRunState(cache: InvalidatingCache): Promise<void> {
  await Promise.all([
    cache.invalidateQueries({ queryKey: ATTENTION_KEY }),
    cache.invalidateQueries({ queryKey: RUNS_KEY }),
  ]);
}
