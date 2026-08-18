import { cn } from "@/lib/utils";

/**
 * A number riding a nav item.
 *
 * - `total` — grey; how many there are.
 * - `in-flight` — blue; the machine is acting.
 * - `waiting` — amber; something is waiting on you.
 */
export type CountTone = "total" | "in-flight" | "waiting";

const TONE_CLASSES: Record<CountTone, string> = {
  total: "bg-muted text-muted-foreground",
  "in-flight": "bg-accent-bg text-accent",
  waiting: "bg-wait-bg text-wait",
};

/** Hidden at zero: a nav item carrying a `0` is noise, not information. */
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
