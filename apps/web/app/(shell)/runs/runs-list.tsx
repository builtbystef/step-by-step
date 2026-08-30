"use client";

import type { RunSummary } from "@step-by-step/api-client";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import {
  FILTERED_EMPTY,
  GLOBAL_EMPTY,
  STATUS_FILTERS,
  TRIGGER_FILTERS,
  WORKFLOW_EMPTY,
  columnsOf,
  listKind,
  rowAction,
  runDurationMs,
  runHref,
  startedAt,
  triggerLabel,
  type Column,
} from "./presentation";
import { RUNS_PATH, fetchRunPage } from "./queries";

import { RUN, disabledReason } from "../workflows/actions";
import { refusalMessage } from "../workflows/messages";
import { StartRunDialog } from "../workflows/start-run-dialog";
import { useStartRun } from "../workflows/use-start-run";
import { workflowQuery } from "../workflows/[id]/queries";
import { useActiveOrganization } from "../use-active-organization";

import { Callout } from "@/components/primitives/callout";
import { EmptyState } from "@/components/primitives/empty-state";
import { StatusChip } from "@/components/primitives/status-chip";
import { Button } from "@/components/ui/button";
import { useCursorList } from "@/hooks/use-cursor-list";
import { filtersFromSearch } from "@/lib/cursor-list";
import { duration } from "@/lib/duration";
import { relativeTime } from "@/lib/relative-time";
import { cn } from "@/lib/utils";

export function RunsList({ workflowId }: { workflowId?: string }) {
  const { active } = useActiveOrganization();

  if (active === null) {
    return null;
  }

  return <Runs orgId={active.id} workflowId={workflowId} />;
}

function Runs({ orgId, workflowId }: { orgId: string; workflowId?: string }) {
  const searchParams = useSearchParams();
  const urlFilters = filtersFromSearch(searchParams);
  const filters =
    workflowId === undefined ? urlFilters : { ...urlFilters, workflow_id: workflowId };
  const columns = columnsOf(workflowId);
  const startRun = useStartRun();

  const list = useCursorList<RunSummary>({
    path: RUNS_PATH,
    orgId,
    filters,
    fetchPage: ({ cursor, limit }) => fetchRunPage(filters, cursor, limit),
  });

  const workflow = useQuery({
    ...workflowQuery(orgId, workflowId ?? ""),
    enabled: workflowId !== undefined,
  });

  const kind = listKind({
    loaded: !list.loading,
    itemCount: list.items.length,
    filters,
  });
  const runRefusal =
    workflow.data === undefined ? null : disabledReason(RUN, workflow.data.draft_state);
  const refused = list.error ?? startRun.refusal;

  return (
    <>
      {kind === "rows" || kind === "filtered" ? (
        <div className="flex items-center gap-2">
          <select
            aria-label="Status"
            className="h-9 rounded-md border border-line bg-panel px-2 text-half text-ink"
            value={filters.status ?? ""}
            onChange={(chosen) => {
              list.setFilter("status", chosen.target.value);
            }}
          >
            {STATUS_FILTERS.map((option) => (
              <option key={option.value || "any"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            aria-label="Trigger"
            className="h-9 rounded-md border border-line bg-panel px-2 text-half text-ink"
            value={filters.trigger ?? ""}
            onChange={(chosen) => {
              list.setFilter("trigger", chosen.target.value);
            }}
          >
            {TRIGGER_FILTERS.map((option) => (
              <option key={option.value || "any"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      ) : null}

      {refused ? <Callout tone="bad">{refusalMessage(refused)}</Callout> : null}

      {kind === "empty" ? (
        workflowId === undefined ? (
          <EmptyState
            absence={GLOBAL_EMPTY.absence}
            whatFillsIt={GLOBAL_EMPTY.whatFillsIt}
            action={<Button render={<Link href="/workflows" />}>{GLOBAL_EMPTY.action}</Button>}
          />
        ) : (
          <EmptyState
            absence={WORKFLOW_EMPTY.absence}
            whatFillsIt={WORKFLOW_EMPTY.whatFillsIt}
            action={
              <Button
                disabled={runRefusal !== null || workflow.data === undefined}
                title={runRefusal ?? undefined}
                onClick={() => {
                  if (workflow.data !== undefined) {
                    startRun.begin(workflow.data);
                  }
                }}
              >
                {WORKFLOW_EMPTY.action}
              </Button>
            }
          />
        )
      ) : null}

      {kind === "filtered" || kind === "rows" ? (
        <table className="w-full text-left text-half">
          <thead>
            <tr className="text-micro font-semibold tracking-wide text-mut uppercase">
              {columns.map((column) => (
                <th key={column} className={cn("px-2 py-2", column === "action" && "w-10")}>
                  {columnHeader(column)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {kind === "filtered" ? (
              <tr>
                <td colSpan={columns.length} className="px-2 py-4 text-mut">
                  {FILTERED_EMPTY}
                </td>
              </tr>
            ) : (
              list.items.map((run) => <RunRow key={run.id} run={run} columns={columns} />)
            )}
          </tbody>
        </table>
      ) : null}

      {list.hasMore ? (
        <Button
          variant="ghost"
          className="self-center text-small"
          disabled={list.fetchingMore}
          onClick={() => {
            list.loadMore();
          }}
        >
          Load more
        </Button>
      ) : null}

      <StartRunDialog
        open={startRun.dialog !== null}
        variables={startRun.dialog?.variables ?? []}
        pending={startRun.pending}
        refusal={startRun.refusal ? refusalMessage(startRun.refusal) : null}
        onSubmit={(row) => {
          if (startRun.dialog !== null) {
            startRun.startFromGrid(startRun.dialog.workflowId, startRun.dialog.variables, row);
          }
        }}
        onOpenChange={(open) => {
          if (!open) {
            startRun.close();
          }
        }}
      />
    </>
  );
}

function columnHeader(column: Column): string {
  if (column === "id") return "Run";
  if (column === "action") return "";
  return column;
}

function RunRow({ run, columns }: { run: RunSummary; columns: readonly Column[] }) {
  const router = useRouter();
  const href = runHref(run.id);
  const action = rowAction(run.status);
  const length = runDurationMs(run);

  return (
    <tr className="group relative border-t border-line hover:bg-accent-bg/40">
      {columns.map((column) => {
        if (column === "status") {
          return (
            <td key={column} className="px-2 py-2">
              <Link href={href} className="after:absolute after:inset-0 after:content-['']">
                <StatusChip state={run.status} />
              </Link>
            </td>
          );
        }
        if (column === "workflow") {
          return (
            <td key={column} className="px-2 py-2 font-semibold">
              {run.workflow_name}
            </td>
          );
        }
        if (column === "trigger") {
          return (
            <td key={column} className="px-2 py-2 text-mut">
              {triggerLabel(run.trigger)}
            </td>
          );
        }
        if (column === "started") {
          return (
            <td key={column} className="px-2 py-2 text-mut">
              {relativeTime(startedAt(run))}
            </td>
          );
        }
        if (column === "duration") {
          return (
            <td key={column} className="px-2 py-2 text-mut">
              {length === null ? "—" : duration(length)}
            </td>
          );
        }
        if (column === "id") {
          return (
            <td key={column} className="px-2 py-2 font-mono text-micro text-mut">
              {run.id}
            </td>
          );
        }
        return (
          <td key={column} className="relative z-10 px-2 py-2 text-right">
            {action === "take-control" ? (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  router.push(href);
                }}
              >
                Take control
              </Button>
            ) : (
              <ChevronRight className="ml-auto size-4 text-mut" />
            )}
          </td>
        );
      })}
    </tr>
  );
}
