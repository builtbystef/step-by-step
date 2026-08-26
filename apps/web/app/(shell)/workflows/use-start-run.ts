"use client";

import {
  getWorkflowVersion,
  startRun,
  type Variable,
  type WorkflowSummary,
} from "@step-by-step/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { runHref } from "../runs/presentation";
import { needsValueGrid, startBody } from "./start-run";

import { columnsOf, type GridRow } from "@/components/value-grid/grid";
import { invalidateRunState } from "@/lib/attention";

/**
 * The Run action on the list row and the Workflow header.
 *
 * Immediate when the published Version declares no Variables; the one-row
 * value grid when it declares some. Starting invalidates the Runs list and
 * the attention query together, then navigates to the new Run.
 */

export function useStartRun(): {
  begin: (workflow: Pick<WorkflowSummary, "id" | "published_version">) => void;
  dialog: { workflowId: string; variables: Variable[] } | null;
  pending: boolean;
  refusal: unknown;
  startFromGrid: (workflowId: string, variables: Variable[], row: GridRow) => void;
  close: () => void;
} {
  const router = useRouter();
  const cache = useQueryClient();
  const [dialog, setDialog] = useState<{ workflowId: string; variables: Variable[] } | null>(null);
  const [refusal, setRefusal] = useState<unknown>(null);

  const start = useMutation({
    mutationFn: async ({
      workflowId,
      variables,
    }: {
      workflowId: string;
      variables: Record<string, string>;
    }) => {
      const { data, error } = await startRun({
        path: { workflow_id: workflowId },
        body: { variables },
      });
      if (error) throw error;
      if (data === undefined) {
        throw new Error("empty start");
      }
      return data;
    },
    onSuccess: async (created) => {
      setDialog(null);
      setRefusal(null);
      await invalidateRunState(cache);
      router.push(runHref(created.run_id));
    },
    onError: (error) => {
      setRefusal(error);
    },
  });

  const begin = (workflow: Pick<WorkflowSummary, "id" | "published_version">) => {
    const version = workflow.published_version;
    if (version === undefined || version === null) {
      return;
    }
    setRefusal(null);
    void (async () => {
      const { data, error } = await getWorkflowVersion({
        path: { workflow_id: workflow.id, number: version },
      });
      if (error) {
        setRefusal(error);
        return;
      }
      const variables = data.variables ?? [];
      if (!needsValueGrid(variables)) {
        start.mutate({ workflowId: workflow.id, variables: {} });
        return;
      }
      setDialog({ workflowId: workflow.id, variables });
    })();
  };

  return {
    begin,
    dialog,
    pending: start.isPending,
    refusal: start.error ?? refusal,
    startFromGrid: (workflowId, variables, row) => {
      start.mutate({
        workflowId,
        variables: startBody(row, columnsOf(variables)).variables,
      });
    },
    close: () => {
      setDialog(null);
      setRefusal(null);
      start.reset();
    },
  };
}
