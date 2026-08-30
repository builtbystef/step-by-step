import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type AttributeTone = "neutral" | "accent" | "wait" | "human" | "ok" | "bad";

const TONE_CLASSES: Record<AttributeTone, string> = {
  neutral: "bg-muted text-muted-foreground",
  accent: "bg-accent-bg text-accent",
  wait: "bg-wait-bg text-wait",
  human: "bg-human-bg text-human",
  ok: "bg-ok-bg text-ok",
  bad: "bg-bad-bg text-bad",
};

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
