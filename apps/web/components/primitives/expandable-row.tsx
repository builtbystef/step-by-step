"use client";

import { ChevronRight } from "lucide-react";
import { useState, type ReactNode } from "react";

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

/**
 * A table row that expands in place: a rotating caret in the first cell and a
 * tinted body beneath. Schedules and Batch rows use it.
 *
 * NEVER the Runs list — a Run's cockpit is a full screen with a live browser
 * pane, so its rows navigate.
 *
 * `columnCount` is the table's full column count, so the body spans the row.
 */
export function ExpandableRow({
  cells,
  columnCount,
  defaultOpen = false,
  expandLabel = "Expand row",
  className,
  onOpenChange,
  children,
}: {
  cells: ReactNode;
  columnCount: number;
  defaultOpen?: boolean;
  expandLabel?: string;
  className?: string;
  onOpenChange?: (open: boolean) => void;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <Collapsible
      render={<tbody />}
      className={cn("border-b", className)}
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        onOpenChange?.(next);
      }}
    >
      <tr>
        <td className="w-8 pl-2 align-middle">
          <CollapsibleTrigger
            aria-label={expandLabel}
            className="flex size-6 items-center justify-center rounded-md text-muted-foreground hover:bg-muted"
          >
            <ChevronRight
              aria-hidden
              className={cn("size-4 transition-transform", open && "rotate-90")}
            />
          </CollapsibleTrigger>
        </td>
        {cells}
      </tr>
      <CollapsibleContent render={<tr />} className="bg-muted">
        <td colSpan={columnCount} className="px-4 py-3 text-half">
          {children}
        </td>
      </CollapsibleContent>
    </Collapsible>
  );
}
