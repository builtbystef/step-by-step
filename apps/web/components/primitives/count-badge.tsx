import { cn } from "@/lib/utils";

export type CountTone = "total" | "in-flight" | "waiting";

const TONE_CLASSES: Record<CountTone, string> = {
  total: "bg-muted text-muted-foreground",
  "in-flight": "bg-accent-bg text-accent",
  waiting: "bg-wait-bg text-wait",
};

export function CountBadge({
  count,
  tone = "total",
  className,
}: {
  count: number;
  tone?: CountTone;
  className?: string;
}) {
  if (count <= 0) {
    return null;
  }

  return (
    <span
      className={cn(
        "inline-flex min-w-5 items-center justify-center rounded-full px-1.5 py-0.5 text-micro font-semibold tabular-nums",
        TONE_CLASSES[tone],
        className,
      )}
    >
      {count}
    </span>
  );
}
