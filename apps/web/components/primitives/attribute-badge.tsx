import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/** The hues an attribute may take. Grey is the default: most properties are facts, not signals. */
export type AttributeTone = "neutral" | "accent" | "wait" | "human" | "ok" | "bad";

const TONE_CLASSES: Record<AttributeTone, string> = {
  neutral: "bg-muted text-muted-foreground",
  accent: "bg-accent-bg text-accent",
  wait: "bg-wait-bg text-wait",
  human: "bg-human-bg text-human",
  ok: "bg-ok-bg text-ok",
  bad: "bg-bad-bg text-bad",
};

/**
 * A property of a thing — selector health, a Draft's publish state, whether a
 * Schedule is on or paused. Rectangular, so that it never reads as a chip.
 *
 * NEVER a lifecycle state. A state that a Run, an Occurrence, or a Batch row
 * can be in is a `StatusChip`, whatever shape would look better in the row.
 */
export function AttributeBadge({
  tone = "neutral",
  className,
  children,
}: {
  tone?: AttributeTone;
  className?: string;
  children: ReactNode;
}) {
  return (
    <Badge className={cn("rounded-md text-micro font-semibold", TONE_CLASSES[tone], className)}>
      {children}
    </Badge>
  );
}
