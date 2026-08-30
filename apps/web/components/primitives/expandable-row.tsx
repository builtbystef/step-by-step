"use client";

import { ChevronRight } from "lucide-react";
import { useState, type ReactNode } from "react";

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

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
