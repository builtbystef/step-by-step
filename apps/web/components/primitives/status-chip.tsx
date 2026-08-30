import { Badge } from "@/components/ui/badge";
import {
  isLiveState,
  lifecycleLabel,
  lifecycleTone,
  type LifecycleState,
  type LifecycleTone,
} from "@/lib/labels";
import { cn } from "@/lib/utils";

const TONE_CLASSES: Record<LifecycleTone, string> = {
  neutral: "bg-muted text-muted-foreground",
  accent: "bg-accent-bg text-accent",
  wait: "bg-wait-bg text-wait",
  ok: "bg-ok-bg text-ok",
  bad: "bg-bad-bg text-bad",
};

export function StatusChip({ state, className }: { state: LifecycleState; className?: string }) {
  const live = isLiveState(state);

  return (
    <Badge
      className={cn(
        "rounded-full text-small font-semibold",
        TONE_CLASSES[lifecycleTone(state)],
        className,
      )}
    >
      {live ? (
        <span
          aria-hidden
          className={cn("size-1.5 rounded-full bg-current", state === "running" && "animate-pulse")}
        />
      ) : null}
      {lifecycleLabel(state)}
    </Badge>
  );
}
