"use client";

import type { WorkflowSummary } from "@step-by-step/api-client";

import { deletionConsequence } from "./messages";

import { Callout } from "@/components/primitives/callout";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export function DeleteDialog({
  workflow,
  pending,
  refusal,
  onConfirm,
  onOpenChange,
}: {
  workflow: WorkflowSummary | null;
  pending: boolean;
  refusal: string | null;
  onConfirm: () => void;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={workflow !== null} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete {workflow?.name}?</DialogTitle>
          <DialogDescription>
            {workflow === null ? "" : deletionConsequence(workflow)}
          </DialogDescription>
        </DialogHeader>
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
          <Button variant="destructive" disabled={pending} onClick={onConfirm}>
            Delete
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
