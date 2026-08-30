import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

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
