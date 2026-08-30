"use client";

import { useEffect, useState } from "react";

import type { Variable } from "@step-by-step/api-client";

import { ValueGrid, initialRows, type GridRow } from "@/components/value-grid";
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

export function StartRunDialog({
  open,
  variables,
  pending,
  refusal,
  onSubmit,
  onOpenChange,
}: {
  open: boolean;
  variables: Variable[];
  pending: boolean;
  refusal: string | null;
  onSubmit: (row: GridRow) => void;
  onOpenChange: (open: boolean) => void;
}) {
  const [rows, setRows] = useState<GridRow[]>(() => initialRows(variables, 1));

  useEffect(() => {
    if (open) {
      setRows(initialRows(variables, 1));
    }
  }, [open, variables]);

  const row = rows[0] ?? initialRows(variables, 1)[0] ?? {};

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <form
          className="flex flex-col gap-4"
          onSubmit={(submitted) => {
            submitted.preventDefault();
            onSubmit(row);
          }}
        >
          <DialogHeader>
            <DialogTitle>Run</DialogTitle>
            <DialogDescription>
              Values for this Run of the published Version. Secret Variables stay in the vault.
            </DialogDescription>
          </DialogHeader>
          <ValueGrid variables={variables} rows={rows} fixedRowCount={1} onChange={setRows} />
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
            <Button type="submit" disabled={pending}>
              Run
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
