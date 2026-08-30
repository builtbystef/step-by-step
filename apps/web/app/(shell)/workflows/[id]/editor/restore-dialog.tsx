"use client";

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

export function RestoreDialog({
  version,
  consequence,
  unsaved,
  pending,
  refusal,
  onConfirm,
  onOpenChange,
}: {
  version: number | null;
  consequence: string;
  unsaved: boolean;
  pending: boolean;
  refusal: string | null;
  onConfirm: () => void;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={version !== null} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            Restore v{version === null ? "" : String(version)} to the Draft?
          </DialogTitle>
          <DialogDescription>{consequence}</DialogDescription>
        </DialogHeader>
        {unsaved ? (
          <Callout tone="warn">
            The Draft also has edits you have not saved. Restoring discards them.
          </Callout>
        ) : null}
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
          <Button disabled={pending} onClick={onConfirm}>
            Restore
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
