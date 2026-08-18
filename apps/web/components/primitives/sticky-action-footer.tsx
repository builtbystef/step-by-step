import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * The bottom-anchored action bar on the creation pages. It stays with the
 * viewport so that a long form never hides the button that finishes it.
 */
export function StickyActionFooter({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "sticky bottom-0 z-10 flex items-center justify-end gap-2 border-t bg-card px-4 py-3",
        className,
      )}
    >
      {children}
    </div>
  );
}
