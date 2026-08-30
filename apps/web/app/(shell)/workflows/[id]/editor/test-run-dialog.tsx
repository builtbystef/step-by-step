"use client";

import { startRun } from "@step-by-step/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { testRunBody, type TestRunField } from "./test-run";

import { refusalMessage } from "../../messages";
import { runHref } from "../../../runs/presentation";

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
import { invalidateRunState } from "@/lib/attention";

export function TestRunDialog({
  open,
  workflowId,
  fields,
  onOpenChange,
}: {
  open: boolean;
  workflowId: string;
  fields: TestRunField[];
  onOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const cache = useQueryClient();
  const [values, setValues] = useState<Record<string, string>>({});

  useEffect(() => {
    if (open) {
      setValues(Object.fromEntries(fields.map((field) => [field.name, ""])));
    }
  }, [open, fields]);

  const start = useMutation({
    mutationFn: async () => {
      const { data, error } = await startRun({
        path: { workflow_id: workflowId },
        body: testRunBody(values, fields),
      });
      if (error) throw error;
      if (data === undefined) {
        throw new Error("empty start");
      }
      return data;
    },
    onSuccess: async (created) => {
      onOpenChange(false);
      await invalidateRunState(cache);
      router.push(runHref(created.run_id));
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
            <DialogTitle>Test run</DialogTitle>
            <DialogDescription>
              Runs this Draft as it is saved. No Version is minted — Schedules and Batches keep
              executing the latest published Version.
            </DialogDescription>
          </DialogHeader>
          {fields.length === 0 ? (
            <p className="text-half text-mut">This Draft declares no Variables.</p>
          ) : (
            <div className="flex flex-col gap-3">
              {fields.map((field) => (
                <div key={field.name} className="flex flex-col gap-1.5">
                  <Label htmlFor={`test-run-${field.name}`}>{field.name}</Label>
                  <Input
                    id={`test-run-${field.name}`}
                    type={field.secret ? "password" : "text"}
                    value={values[field.name] ?? ""}
                    autoComplete="off"
                    onChange={(typed) => {
                      setValues((current) => ({ ...current, [field.name]: typed.target.value }));
                    }}
                  />
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
              Test run
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
