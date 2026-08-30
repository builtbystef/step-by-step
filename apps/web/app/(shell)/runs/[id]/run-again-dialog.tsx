"use client";

import { startRun, type Variable } from "@step-by-step/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { refusalMessage } from "./messages";
import { runAgainValues } from "./presentation";

import { Callout } from "@/components/primitives/callout";
import { LockedCell } from "@/components/primitives/locked-cell";
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
import { invalidateRunState } from "@/lib/attention";

export function RunAgainDialog({
  open,
  workflowId,
  declared,
  stored,
  onOpenChange,
}: {
  open: boolean;
  workflowId: string;
  declared: Variable[];
  stored: Record<string, unknown>;
  onOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const cache = useQueryClient();
  const rows = runAgainValues(declared, stored);
  const [values, setValues] = useState<Record<string, string>>({});

  useEffect(() => {
    if (open) {
      setValues(Object.fromEntries(rows.map((row) => [row.name, row.value])));
    }
  }, [open, stored, declared]);

  const start = useMutation({
    mutationFn: async () => {
      const variables: Record<string, string> = {};
      for (const row of rows) {
        if (!row.secret) {
          variables[row.name] = values[row.name] ?? "";
        }
      }
      const { data, error } = await startRun({
        path: { workflow_id: workflowId },
        body: { variables },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: async (created) => {
      onOpenChange(false);
      await invalidateRunState(cache);
      router.push(`/runs/${created.run_id}`);
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form
          className="flex flex-col gap-4"
          onSubmit={(submitted) => {
            submitted.preventDefault();
            start.mutate();
          }}
        >
          <DialogHeader>
            <DialogTitle>Run again</DialogTitle>
            <DialogDescription>
              Starts a new Run of the latest published Version, with these Variable values.
            </DialogDescription>
          </DialogHeader>
          {rows.length === 0 ? (
            <p className="text-half text-mut">This Workflow declares no Variables.</p>
          ) : (
            <div className="flex flex-col gap-3">
              {rows.map((row) => (
                <div key={row.name} className="flex flex-col gap-1.5">
                  <Label htmlFor={`run-again-${row.name}`}>{row.name}</Label>
                  {row.secret ? (
                    <LockedCell secretName={row.name} />
                  ) : (
                    <Input
                      id={`run-again-${row.name}`}
                      value={values[row.name] ?? ""}
                      autoComplete="off"
                      onChange={(typed) => {
                        setValues((current) => ({ ...current, [row.name]: typed.target.value }));
                      }}
                    />
                  )}
                </div>
              ))}
            </div>
          )}
          {start.error ? <Callout tone="bad">{refusalMessage(start.error)}</Callout> : null}
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
            <Button type="submit" disabled={start.isPending}>
              Run
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
