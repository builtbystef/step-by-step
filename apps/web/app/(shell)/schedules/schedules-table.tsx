"use client";

import type { ScheduleSummary } from "@step-by-step/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import {
  hatchOf,
  historyItems,
  holeStory,
  needsValuesBanner,
  noteOf,
  overlapBanner,
  recurrenceHeadline,
  recurrenceSubline,
  runHref,
  runNowRefusal,
  stripMarks,
  type StripMark,
} from "./presentation";
import {
  patchEnabled,
  runNow,
  scheduleDetailKey,
  scheduleDetailQuery,
  schedulesKey,
  schedulesQuery,
} from "./queries";

import { occurrenceLabel } from "../workflows/[id]/schedules/creation";

import { Callout } from "@/components/primitives/callout";
import { ExpandableRow } from "@/components/primitives/expandable-row";
import { HatchedOccurrence } from "@/components/primitives/hatched-occurrence";
import { StatusChip } from "@/components/primitives/status-chip";
import { Button } from "@/components/ui/button";
import { invalidateRunState } from "@/lib/attention";

const COLUMN_COUNT = 7;

/**
 * The Schedules table content: the row and its expansion. The shell spec
 * mounts this on the global route and the Workflow's Schedules tab; this
 * slice is the content those routes draw.
 */

export function SchedulesTable({ orgId }: { orgId: string }) {
  const list = useQuery(schedulesQuery(orgId));
  const viewerTz = Intl.DateTimeFormat().resolvedOptions().timeZone;

  if (list.error) {
    return <Callout tone="bad">Something went wrong. Try again in a moment.</Callout>;
  }
  if (list.data === undefined) {
    return null;
  }

  return (
    <table className="w-full text-left text-half">
      <thead>
        <tr className="text-micro font-semibold tracking-wide text-mut uppercase">
          <th className="w-8" />
          <th className="px-2 py-2">On</th>
          <th className="px-2 py-2">Workflow</th>
          <th className="px-2 py-2">Recurrence</th>
          <th className="px-2 py-2">Next due</th>
          <th className="px-2 py-2">Last run</th>
          <th className="px-2 py-2">Note</th>
        </tr>
      </thead>
      {list.data.map((schedule) => (
        <ScheduleRow key={schedule.id} orgId={orgId} schedule={schedule} viewerTz={viewerTz} />
      ))}
    </table>
  );
}

function ScheduleRow({
  orgId,
  schedule,
  viewerTz,
}: {
  orgId: string;
  schedule: ScheduleSummary;
  viewerTz: string;
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
      await cache.invalidateQueries({ queryKey: schedulesKey(orgId) });
    },
  });

  return (
    <ExpandableRow
      columnCount={COLUMN_COUNT}
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
          <td className="px-2 py-2 align-middle font-semibold">{schedule.workflow_name}</td>
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
      await cache.invalidateQueries({ queryKey: schedulesKey(orgId) });
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
            <Button size="sm" variant="outline" render={<Link href={missing.setValuesHref} />}>
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
              <Button size="sm" variant="outline" render={<Link href={overlap.openHref} />}>
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
