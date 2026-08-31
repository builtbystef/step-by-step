"use client";

import type { ScheduleSummary } from "@step-by-step/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import {
  FILTERED_EMPTY,
  GLOBAL_EMPTY,
  WORKFLOW_EMPTY,
  columnsOf,
  hatchOf,
  historyItems,
  holeStory,
  listKind,
  needsValuesBanner,
  noteOf,
  overlapBanner,
  recurrenceHeadline,
  recurrenceSubline,
  runHref,
  runNowRefusal,
  stripMarks,
  type Column,
  type StripMark,
} from "./presentation";
import {
  SCHEDULES_KEY,
  SCHEDULES_PATH,
  fetchSchedulePage,
  patchEnabled,
  runNow,
  scheduleDetailKey,
  scheduleDetailQuery,
} from "./queries";

import { occurrenceLabel } from "../workflows/[id]/schedules/creation";
import { newSchedulePath } from "../workflows/[id]/tabs";
import { NEW_SCHEDULE, disabledReason } from "../workflows/actions";
import { refusalMessage } from "../workflows/messages";
import { workflowQuery } from "../workflows/[id]/queries";
import { useActiveOrganization } from "../use-active-organization";

import { Callout } from "@/components/primitives/callout";
import { EmptyState } from "@/components/primitives/empty-state";
import { ExpandableRow } from "@/components/primitives/expandable-row";
import { HatchedOccurrence } from "@/components/primitives/hatched-occurrence";
import { StatusChip } from "@/components/primitives/status-chip";
import { Button } from "@/components/ui/button";
import { useCursorList } from "@/hooks/use-cursor-list";
import { filtersFromSearch } from "@/lib/cursor-list";
import { invalidateRunState } from "@/lib/attention";

export function SchedulesList({ workflowId }: { workflowId?: string }) {
  const { active } = useActiveOrganization();

  if (active === null) {
    return null;
  }

  return <Schedules orgId={active.id} workflowId={workflowId} />;
}

function Schedules({ orgId, workflowId }: { orgId: string; workflowId?: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlFilters = filtersFromSearch(searchParams);
  const filters =
    workflowId === undefined ? urlFilters : { ...urlFilters, workflow_id: workflowId };
  const columns = columnsOf(workflowId);
  const viewerTz = Intl.DateTimeFormat().resolvedOptions().timeZone;

  const list = useCursorList<ScheduleSummary>({
    path: SCHEDULES_PATH,
    orgId,
    filters,
    fetchPage: ({ cursor, limit }) => fetchSchedulePage(filters, cursor, limit),
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
  const scheduleRefusal =
    workflow.data === undefined ? null : disabledReason(NEW_SCHEDULE, workflow.data.draft_state);
  const columnCount = columns.length + 1;

  return (
    <>
      {list.error ? <Callout tone="bad">{refusalMessage(list.error)}</Callout> : null}

      {kind === "empty" ? (
        workflowId === undefined ? (
          <EmptyState
            absence={GLOBAL_EMPTY.absence}
            whatFillsIt={GLOBAL_EMPTY.whatFillsIt}
            action={
              <Button nativeButton={false} render={<Link href="/workflows" />}>
                {GLOBAL_EMPTY.action}
              </Button>
            }
          />
        ) : (
          <EmptyState
            absence={WORKFLOW_EMPTY.absence}
            whatFillsIt={WORKFLOW_EMPTY.whatFillsIt}
            action={
              <Button
                disabled={scheduleRefusal !== null || workflow.data === undefined}
                title={scheduleRefusal ?? undefined}
                onClick={() => {
                  router.push(newSchedulePath(workflowId));
                }}
              >
                {WORKFLOW_EMPTY.action}
              </Button>
            }
          />
        )
      ) : null}

      {kind === "filtered" || kind === "rows" ? (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-half">
            <thead>
              <tr className="text-micro font-semibold tracking-wide text-mut uppercase">
                <th className="w-8" />
                {columns.map((column) => (
                  <th key={column} className="px-2 py-2">
                    {columnHeader(column)}
                  </th>
                ))}
              </tr>
            </thead>
            {kind === "filtered" ? (
              <tbody>
                <tr>
                  <td colSpan={columnCount} className="px-2 py-4 text-mut">
                    {FILTERED_EMPTY}
                  </td>
                </tr>
              </tbody>
            ) : (
              list.items.map((schedule) => (
                <ScheduleRow
                  key={schedule.id}
                  orgId={orgId}
                  schedule={schedule}
                  viewerTz={viewerTz}
                  showWorkflow={workflowId === undefined}
                  columnCount={columnCount}
                />
              ))
            )}
          </table>
        </div>
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
    </>
  );
}

function columnHeader(column: Column): string {
  if (column === "enabled") return "On";
  if (column === "next-due") return "Next due";
  if (column === "last-run") return "Last run";
  return column;
}

function ScheduleRow({
  orgId,
  schedule,
  viewerTz,
  showWorkflow,
  columnCount,
}: {
  orgId: string;
  schedule: ScheduleSummary;
  viewerTz: string;
  showWorkflow: boolean;
  columnCount: number;
}) {
  const cache = useQueryClient();
  const [open, setOpen] = useState(false);
  const headline = recurrenceHeadline(schedule.cron);
  const sub = recurrenceSubline(schedule.cron, schedule.timezone);
  const note = noteOf(schedule.latest_occurrence, schedule.missing_variable_names);
  const nextDue =
    schedule.next_due_at === null
      ? null
      : occurrenceLabel(schedule.next_due_at, schedule.timezone, viewerTz);

  const toggle = useMutation({
    mutationFn: (enabled: boolean) => patchEnabled(schedule.id, enabled),
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: SCHEDULES_KEY });
    },
  });

  return (
    <ExpandableRow
      columnCount={columnCount}
      expandLabel={`Expand ${schedule.workflow_name}`}
      onOpenChange={setOpen}
      cells={
        <>
          <td className="px-2 py-2 align-middle">
            <input
              type="checkbox"
              aria-label={`Enable ${schedule.workflow_name}`}
              className="size-4 accent-accent"
              checked={schedule.enabled}
              onChange={(event) => {
                toggle.mutate(event.target.checked);
              }}
            />
          </td>
          {showWorkflow ? (
            <td className="px-2 py-2 align-middle font-semibold">{schedule.workflow_name}</td>
          ) : null}
          <td className="px-2 py-2 align-middle">
            <div>{headline}</div>
            <div className="font-mono text-micro text-mut">
              {sub.cron} · {sub.timezone}
            </div>
          </td>
          <td className="px-2 py-2 align-middle">
            {nextDue === null ? (
              ""
            ) : (
              <>
                <div>{nextDue.at}</div>
                {nextDue.local === null ? null : (
                  <div className="text-micro text-mut">{nextDue.local}</div>
                )}
              </>
            )}
          </td>
          <td className="px-2 py-2 align-middle">
            {schedule.last_run === null ? "" : <StatusChip state={schedule.last_run.status} />}
          </td>
          <td className="px-2 py-2 align-middle text-wait">{note}</td>
        </>
      }
    >
      {open ? <ScheduleExpansion orgId={orgId} schedule={schedule} viewerTz={viewerTz} /> : null}
    </ExpandableRow>
  );
}

function ScheduleExpansion({
  orgId,
  schedule,
  viewerTz,
}: {
  orgId: string;
  schedule: ScheduleSummary;
  viewerTz: string;
}) {
  const cache = useQueryClient();
  const detail = useQuery(scheduleDetailQuery(orgId, schedule.id));
  const missing = needsValuesBanner({
    state: schedule.state,
    missingVariableNames: schedule.missing_variable_names,
    workflowId: schedule.workflow_id,
    scheduleId: schedule.id,
  });
  const overlap = schedule.latest_occurrence ? overlapBanner(schedule.latest_occurrence) : null;
  const paused = !schedule.enabled;

  const fire = useMutation({
    mutationFn: () => runNow(schedule.id),
    onSuccess: async () => {
      await invalidateRunState(cache);
      await cache.invalidateQueries({ queryKey: SCHEDULES_KEY });
      await cache.invalidateQueries({ queryKey: scheduleDetailKey(orgId, schedule.id) });
    },
  });
  const refused = runNowRefusal(fire.error);

  if (detail.error) {
    return <Callout tone="bad">Something went wrong. Try again in a moment.</Callout>;
  }
  if (detail.data === undefined) {
    return null;
  }

  const history = detail.data.history;
  const marks = stripMarks({
    history,
    nextOccurrences: detail.data.next_occurrences,
    paused,
  });
  const items = historyItems(history);
  const latest = schedule.latest_occurrence;
  const hole =
    latest !== null && latest.reason !== "overlap"
      ? holeStory(latest.reason, schedule.missing_variable_names)
      : null;
  const overlapAt =
    overlap !== null && latest !== null
      ? occurrenceLabel(latest.occurrence_at, schedule.timezone, viewerTz).at
      : null;

  return (
    <div className="flex flex-col gap-3">
      {missing ? (
        <Callout
          tone={missing.tone}
          title="This Schedule cannot fire"
          actions={
            <Button
              size="sm"
              variant="outline"
              nativeButton={false}
              render={<Link href={missing.setValuesHref} />}
            >
              {missing.setValuesLabel}
            </Button>
          }
        >
          {holeStory("missing_values", missing.names)}
        </Callout>
      ) : null}

      {overlap !== null && overlapAt !== null ? (
        <Callout
          tone="warn"
          title={`${overlapAt} did not run`}
          actions={
            <>
              <Button
                size="sm"
                variant="outline"
                nativeButton={false}
                render={<Link href={overlap.openHref} />}
              >
                {overlap.openLabel}
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={fire.isPending}
                onClick={() => {
                  fire.mutate();
                }}
              >
                {overlap.runNowLabel}
              </Button>
            </>
          }
        >
          {overlap.story}
        </Callout>
      ) : hole !== null && latest !== null && missing === null ? (
        <Callout tone={latest.reason === "missing_values" ? "bad" : "info"}>
          {occurrenceLabel(latest.occurrence_at, schedule.timezone, viewerTz).at} did not run.{" "}
          {hole}
        </Callout>
      ) : null}

      {refused ? <Callout tone="bad">{refused}</Callout> : null}

      <OccurrenceStrip marks={marks} timezone={schedule.timezone} viewerTz={viewerTz} />

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <h3 className="text-micro font-semibold tracking-wide text-mut uppercase">
            Next occurrences
          </h3>
          {paused ? (
            <p className="text-mut">Nothing ahead.</p>
          ) : (
            <ol>
              {detail.data.next_occurrences.map((iso) => {
                const shown = occurrenceLabel(iso, schedule.timezone, viewerTz);
                return (
                  <li key={iso} className="flex flex-wrap gap-2 py-0.5">
                    <span>{shown.at}</span>
                    {shown.local === null ? null : <span className="text-mut">{shown.local}</span>}
                  </li>
                );
              })}
            </ol>
          )}
        </div>
        <div>
          <h3 className="text-micro font-semibold tracking-wide text-mut uppercase">Recent</h3>
          <ol>
            {items.map((item) => (
              <li
                key={`${item.kind}-${item.at}`}
                className="flex flex-wrap items-center gap-2 py-0.5"
              >
                <span className="text-mut">
                  {occurrenceLabel(item.at, schedule.timezone, viewerTz).at}
                </span>
                {item.kind === "run" ? (
                  <>
                    <StatusChip state={item.status} />
                    <Link href={runHref(item.runId)} className="text-accent hover:underline">
                      Open
                    </Link>
                  </>
                ) : (
                  <span>{holeStory(item.reason, schedule.missing_variable_names)}</span>
                )}
              </li>
            ))}
          </ol>
        </div>
      </div>

      <div>
        <h3 className="text-micro font-semibold tracking-wide text-mut uppercase">Values</h3>
        <p className="flex flex-wrap gap-2">
          {Object.entries(schedule.variables).map(([name, value]) => (
            <span key={name} className="text-half">
              {name} = {String(value)}
            </span>
          ))}
        </p>
      </div>
    </div>
  );
}

function OccurrenceStrip({
  marks,
  timezone,
  viewerTz,
}: {
  marks: StripMark[];
  timezone: string;
  viewerTz: string;
}) {
  return (
    <div className="flex items-end gap-1 overflow-x-auto py-1" aria-label="Occurrence strip">
      {marks.map((mark, index) => (
        <StripSlot
          key={`${mark.kind}-${index}`}
          mark={mark}
          timezone={timezone}
          viewerTz={viewerTz}
        />
      ))}
    </div>
  );
}

function StripSlot({
  mark,
  timezone,
  viewerTz,
}: {
  mark: StripMark;
  timezone: string;
  viewerTz: string;
}) {
  if (mark.kind === "paused") {
    return <HatchedOccurrence kind="never-due" label="paused interval" className="w-16" />;
  }
  if (mark.kind === "due") {
    const shown = occurrenceLabel(mark.at, timezone, viewerTz);
    return (
      <span
        role="img"
        title={shown.at}
        aria-label={`due ${shown.at}`}
        className="inline-block h-5 w-3 rounded-sm border border-dashed border-line"
      />
    );
  }
  if (mark.kind === "run") {
    return <StatusChip state={mark.status} />;
  }
  const shown = occurrenceLabel(mark.at, timezone, viewerTz);
  return (
    <HatchedOccurrence kind={hatchOf(mark.kind)} label={`${shown.at} — ${holeStory(mark.kind)}`} />
  );
}
