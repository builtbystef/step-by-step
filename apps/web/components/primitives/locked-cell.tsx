import { Lock } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * A grid cell whose value comes from the vault. Purple, because purple means
 * "a secret, or a human-supplied value".
 *
 * It renders the NAME of the Secret it draws from and never the value — there
 * is no prop to pass one.
 */
export function LockedCell({ secretName, className }: { secretName: string; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-half text-human", className)}>
      <Lock aria-hidden className="size-3.5" />
      <span>{secretName}</span>
    </span>
  );
}
