import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * The shell-level signal that a Run is waiting on the person reading the
 * screen. Amber, page-width across the content column, above the page title,
 * because the deadline it names fails the Run when it passes.
 *
 * Pure over props here: the polling and the countdown tick arrive with the
 * shell slice that mounts it. `countdown` is already-formatted text so that
 * the caller can tick it as fast as it likes, and it reads as a machine
 * string, in monospace.
 */
export function AttentionBand({
  waitingCount,
  runLabel,
  countdown,
  onTakeControl,
  className,
}: {
  waitingCount: number;
  runLabel: string;
  countdown: string;
  onTakeControl: () => void;
  className?: string;
}) {
  if (waitingCount <= 0) {
    return null;
  }

  const others = waitingCount - 1;

  return (
    <div
      role="status"
      className={cn(
        "flex w-full items-center gap-3 border-b border-wait/30 bg-wait-bg px-4 py-2 text-half text-wait",
        className,
      )}
    >
      <span className="font-semibold">
        {runLabel} needs you
        {others > 0 ? ` — and ${String(others)} other ${others === 1 ? "run" : "runs"}` : ""}
      </span>
      <span className="font-mono text-small tabular-nums">{countdown}</span>
      <Button size="sm" className="ml-auto" onClick={onTakeControl}>
        Take control
      </Button>
    </div>
  );
}
