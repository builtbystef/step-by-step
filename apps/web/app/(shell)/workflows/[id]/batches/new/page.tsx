"use client";

import { createBatch, type CreateBatch, type Variable } from "@step-by-step/api-client";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  createBody,
  defaultBatchName,
  progressHref,
  rerunBatchName,
  sequentialEta,
} from "./creation";
import { refusalMessage } from "./messages";
import { loadBatch, workflowBatchesQuery } from "./queries";

import { versionDocumentQuery } from "../../editor/queries";
import { workflowQuery } from "../../queries";

import { useActiveOrganization } from "../../../../use-active-organization";

import {
  ValueGrid,
  applyCopiedBatch,
  columnsOf,
  initialRows,
  rowCounts,
  type GridRow,
} from "@/components/value-grid";
import { Callout } from "@/components/primitives/callout";
import { StickyActionFooter } from "@/components/primitives/sticky-action-footer";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { COPY } from "@/lib/copy";

/**
 * One page, always a grid. Columns are the Workflow's declared Variables;
 * typing, pasting, and copying a past Batch's rows all land in this table.
 * Submitting creates the Batch and navigates to its progress view.
 */

export default function NewBatchPage() {
  const { active } = useActiveOrganization();
  const params = useParams<{ id: string }>();

  if (active === null) {
    return null;
  }

  return <NewBatch orgId={active.id} workflowId={params.id} />;
}

function NewBatch({ orgId, workflowId }: { orgId: string; workflowId: string }) {
  const router = useRouter();
  const workflow = useQuery(workflowQuery(orgId, workflowId));
  const published = workflow.data?.published_version ?? null;
  const document = useQuery(versionDocumentQuery(orgId, workflowId, published));
  const past = useQuery(workflowBatchesQuery(orgId, workflowId));

  const variables: Variable[] = document.data?.variables ?? [];
  const columns = columnsOf(variables);

  const [rows, setRows] = useState<GridRow[] | null>(null);
  const [name, setName] = useState<string | null>(null);
  const [runIncomplete, setRunIncomplete] = useState(false);

  useEffect(() => {
    if (document.data === undefined || rows !== null) {
      return;
    }
    setRows(initialRows(document.data.variables ?? [], 1));
  }, [document.data, rows]);

  const copy = useMutation({
    mutationFn: async (batchId: string) => {
      const detail = await loadBatch(batchId);
      return detail;
    },
    onSuccess: (detail) => {
      setRows(applyCopiedBatch(columns, detail.rows));
      const workflowName = workflow.data?.name ?? "";
      setName(rerunBatchName(workflowName, detail.batch.name));
    },
  });

  const create = useMutation({
    mutationFn: async (body: CreateBatch) => {
      const { data, error } = await createBatch({
        path: { workflow_id: workflowId },
        body,
      });
      if (error) throw error;
      return data;
    },
    onSuccess: (created) => {
      router.push(progressHref(created.batch_id));
    },
  });

  if (workflow.error) {
    return <Callout tone="bad">{refusalMessage(workflow.error)}</Callout>;
  }
  if (document.error) {
    return <Callout tone="bad">{refusalMessage(document.error)}</Callout>;
  }
  if (published === null && workflow.data !== undefined) {
    return <Callout tone="bad">{COPY.noPublishedVersion}</Callout>;
  }
  if (workflow.data === undefined || document.data === undefined || rows === null) {
    return null;
  }

  const shownName = name ?? defaultBatchName(workflow.data.name, new Date());
  const counts = rowCounts(rows, columns);
  const eta = sequentialEta(rows.length, workflow.data.recent_run_median_ms);
  const refused = copy.error ?? create.error;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-title font-semibold">New batch</h2>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button variant="secondary" size="sm" className="ml-auto">
                Copy from a past Batch
              </Button>
            }
          />
          <DropdownMenuContent align="end" className="min-w-56">
            {(past.data ?? []).length === 0 ? (
              <DropdownMenuItem disabled>No past Batches yet</DropdownMenuItem>
            ) : (
              (past.data ?? []).map((batch) => (
                <DropdownMenuItem
                  key={batch.id}
                  onClick={() => {
                    copy.mutate(batch.id);
                  }}
                >
                  {batch.name}
                </DropdownMenuItem>
              ))
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {refused ? <Callout tone="bad">{refusalMessage(refused)}</Callout> : null}

      <ValueGrid variables={variables} rows={rows} onChange={setRows} />

      <StickyActionFooter className="flex-wrap justify-between gap-3">
        <div className="mr-auto flex min-w-0 flex-1 flex-col gap-2">
          <label className="flex min-w-0 items-center gap-2 text-small text-mut">
            Name
            <Input
              aria-label="Batch name"
              value={shownName}
              className="h-7 max-w-md text-half"
              onChange={(typed) => {
                setName(typed.target.value);
              }}
            />
          </label>
          <p className="text-small text-mut">
            {String(counts.total)} total · {String(counts.complete)} complete ·{" "}
            {String(counts.missing)} missing a value
          </p>
          <label className="flex items-center gap-2 text-half text-ink">
            <input
              type="checkbox"
              className="size-4 accent-accent"
              checked={runIncomplete}
              onChange={(ticked) => {
                setRunIncomplete(ticked.target.checked);
              }}
            />
            Run them anyway
          </label>
          <p className="text-small text-ink">{eta}</p>
        </div>
        <Button
          disabled={create.isPending || rows.length === 0}
          onClick={() => {
            create.mutate(createBody(shownName, rows, columns, runIncomplete));
          }}
        >
          Create batch
        </Button>
      </StickyActionFooter>
    </div>
  );
}
