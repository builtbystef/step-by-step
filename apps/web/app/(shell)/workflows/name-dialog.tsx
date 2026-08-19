"use client";

import { useEffect, useState } from "react";

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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/**
 * The one dialog that asks for a name: creating a Workflow, and renaming one.
 *
 * One component for both, because they ask the same question and only differ
 * in what they call the button. Creating is name-only by decision — the
 * recording protocol is app-first, so a Workflow is created and named here and
 * recording then targets its Draft.
 */
export function NameDialog({
  open,
  title,
  description,
  submitLabel,
  initialName,
  pending,
  refusal,
  onSubmit,
  onOpenChange,
}: {
  open: boolean;
  title: string;
  description: string;
  submitLabel: string;
  initialName?: string;
  pending: boolean;
  refusal: string | null;
  onSubmit: (name: string) => void;
  onOpenChange: (open: boolean) => void;
}) {
  const [name, setName] = useState(initialName ?? "");

  // Opening is what resets the field: the dialog outlives one use, and a stale
  // name left in it would rename the next Workflow to the last one's.
  useEffect(() => {
    if (open) {
      setName(initialName ?? "");
    }
  }, [open, initialName]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form
          className="flex flex-col gap-4"
          onSubmit={(submitted) => {
            submitted.preventDefault();
            onSubmit(name.trim());
          }}
        >
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription>{description}</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2">
            <Label htmlFor="workflow-name">Name</Label>
            <Input
              id="workflow-name"
              value={name}
              autoFocus
              autoComplete="off"
              onChange={(typed) => {
                setName(typed.target.value);
              }}
            />
          </div>
          {refusal === null ? null : <Callout tone="bad">{refusal}</Callout>}
          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                onOpenChange(false);
              }}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={pending || name.trim() === ""}>
              {submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
