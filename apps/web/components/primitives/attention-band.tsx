import { Button } from "@/components/ui/button";
import { attentionMessage } from "@/lib/attention";
import { cn } from "@/lib/utils";

/**
 * The shell-level signal that a Run is waiting on the person reading the
 * screen. Amber, page-width across the content column, above the page title,
 * because the deadline it names fails the Run when it passes.
 *
 * Pure over props: the shell owns the poll and local tick. `countdown` is
 * already-formatted text, and it reads as a machine string in monospace.
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

  return (
    <div
      role="status"
      className={cn(
        "flex w-full items-center gap-3 border-b border-wait/30 bg-wait-bg px-4 py-2 text-half text-wait",
        className,
      )}
    >
      <span className="font-semibold">{attentionMessage(waitingCount, runLabel)}</span>
      <span className="font-mono text-small tabular-nums">{countdown}</span>
      {/* text-small because shadcn's `sm` button carries a 0.8rem size of its own. */}
      <Button size="sm" className="ml-auto text-small" onClick={onTakeControl}>
        Take control
      </Button>
    </div>
  );
}
