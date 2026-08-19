"use client";

import type { DraftComparison } from "@step-by-step/api-client";
import { Minus, PenLine, Plus } from "lucide-react";
import type { ReactNode } from "react";

import { publishPlan, type DiffSection } from "./publish";

import { Callout } from "@/components/primitives/callout";
import { CountBadge } from "@/components/primitives/count-badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

/**
 * Publishing: what it would change, before it changes it.
 *
 * A Version is what Schedules and Batches execute, so minting one is the one
 * moment the editor stops being private. The modal is therefore a reading of
 * the diff rather than a confirmation of an intention: the Steps by name, in
 * three lists, and the number about to appear on them.
 *
 * Nothing is minted by opening it. The comparison is a read, and the only
 * thing that publishes is the button that says so — which is what makes
 * cancelling free.
 */
export function PublishDialog({
  open,
  comparison,
  pending,
  refusal,
  onConfirm,
  onOpenChange,
}: {
  open: boolean;
  comparison: DraftComparison | null;
  pending: boolean;
  refusal: string | null;
  onConfirm: () => void;
  onOpenChange: (open: boolean) => void;
}) {
  const plan = comparison === null ? null : publishPlan(comparison);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {plan === null ? "Publish" : `Publish v${String(plan.number)}?`}
          </DialogTitle>
          <DialogDescription>
            A Version is what Schedules and Batches execute. It never changes again, and the Draft
            goes on being edited.
          </DialogDescription>
        </DialogHeader>

        {plan === null ? (
          <p className="text-half text-mut">Working out what would change…</p>
        ) : (
          <div className="flex max-h-80 flex-col gap-3 overflow-y-auto">
            {plan.sections.map((section) => (
              <Section key={section.key} section={section} />
            ))}
            {plan.note === null ? null : (
              <Callout tone={plan.worthPublishing ? "info" : "warn"}>{plan.note}</Callout>
            )}
          </div>
        )}

        {refusal === null ? null : <Callout tone="bad">{refusal}</Callout>}

        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => {
              onOpenChange(false);
            }}
          >
            Cancel
          </Button>
          <Button disabled={pending || plan === null || !plan.worthPublishing} onClick={onConfirm}>
            {plan === null ? "Publish" : `Publish v${String(plan.number)}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** The icon and hue each of the three lists is read by. */
const MARKS: Record<DiffSection["key"], { icon: ReactNode; className: string }> = {
  added: { icon: <Plus className="size-3.5" />, className: "text-ok" },
  changed: { icon: <PenLine className="size-3.5" />, className: "text-wait" },
  removed: { icon: <Minus className="size-3.5" />, className: "text-bad" },
};

/** One list of Steps, named the way the cards name them. */
function Section({ section }: { section: DiffSection }) {
  const mark = MARKS[section.key];

  return (
    <div className="flex flex-col gap-1">
      <p className="flex items-center gap-2 text-small font-semibold text-ink">
        {section.heading}
        <CountBadge count={section.steps.length} />
      </p>
      <ul className="flex flex-col gap-1">
        {section.steps.map((step) => (
          <li key={step.id} className="flex items-center gap-2 text-half text-mut">
            <span className={mark.className}>{mark.icon}</span>
            <span className="truncate text-ink">{step.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
