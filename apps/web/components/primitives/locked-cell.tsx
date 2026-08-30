import { Lock } from "lucide-react";

import { cn } from "@/lib/utils";

export function LockedCell({ secretName, className }: { secretName: string; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-half text-human", className)}>
      <Lock aria-hidden className="size-3.5" />
      <span>{secretName}</span>
    </span>
  );
}
