import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/**
 * Three parts, always: one bold sentence naming what is absent, one grey
 * sentence saying what fills it, and one button going there. All three are
 * required, because an empty state missing any of them is a dead end.
 *
 * A filter or a search matching nothing is NOT this: that is a one-line
 * message inside the table, because "you have none" and "none match" lead to
 * two different next actions.
 */
export function EmptyState({
  absence,
  whatFillsIt,
  action,
  className,
}: {
  absence: string;
  whatFillsIt: string;
  action: ReactNode;
  className?: string;
}) {
  return (
    <Card className={cn("items-center gap-2 px-6 py-10 text-center", className)}>
      <p className="text-title font-semibold text-foreground">{absence}</p>
      <p className="text-half text-muted-foreground">{whatFillsIt}</p>
      <div className="mt-2">{action}</div>
    </Card>
  );
}
