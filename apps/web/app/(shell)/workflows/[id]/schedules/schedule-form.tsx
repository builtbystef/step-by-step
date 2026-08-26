"use client";

import {
  createSchedule,
  updateSchedule,
  type CreateSchedule,
  type Variable,
} from "@step-by-step/api-client";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  FREQUENCY_OPTIONS,
  MINUTE_INTERVALS,
  PRESETS,
  WEEKDAY_OPTIONS,
  applyPreset,
  clockValue,
  cronOf,
  defaultTimezone,
  emptyVariableNames,
  lastNonTestVariables,
  occurrenceLabel,
  openExisting,
  scheduleBody,
  schedulesHref,
  withClock,
  withFrequency,
  writeCronInstead,
  type RecurrenceMode,
} from "./creation";
import { emptyValueMessage, refusalMessage } from "./messages";
import {
  instanceQuery,
  scheduleDetailQuery,
  schedulePreviewQuery,
  workflowRunsQuery,
} from "./queries";

import { versionDocumentQuery } from "../editor/queries";
import { workflowQuery } from "../queries";

import {
  ValueGrid,
  applyCopiedBatch,
  columnsOf,
  initialRows,
  submittedVariables,
  type GridRow,
} from "@/components/value-grid";
import { Callout } from "@/components/primitives/callout";
import { StickyActionFooter } from "@/components/primitives/sticky-action-footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { COPY } from "@/lib/copy";
import { humanize, type Recurrence } from "@/lib/recurrence";

/**
 * The creation and edit surface: preset chips, a sentence of dropdowns (or a
 * raw cron field), the preview, and the one-row value set.
 */

export function ScheduleForm({
  orgId,
  workflowId,
  scheduleId,
}: {
  orgId: string;
  workflowId: string;
  scheduleId?: string;
}) {
  const router = useRouter();
  const workflow = useQuery(workflowQuery(orgId, workflowId));
  const published = workflow.data?.published_version ?? null;
  const document = useQuery(versionDocumentQuery(orgId, workflowId, published));
  const instance = useQuery(instanceQuery());
  const existing = useQuery({
    ...scheduleDetailQuery(orgId, scheduleId ?? ""),
    enabled: scheduleId !== undefined,
  });
  const runs = useQuery(workflowRunsQuery(orgId, workflowId));

  const variables: Variable[] = document.data?.variables ?? [];
  const columns = columnsOf(variables);

  const [mode, setMode] = useState<RecurrenceMode | null>(null);
  const [timezone, setTimezone] = useState<string | null>(null);
  const [rows, setRows] = useState<GridRow[] | null>(null);
  const [name, setName] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [attempted, setAttempted] = useState(false);

  useEffect(() => {
    if (mode !== null) {
      return;
    }
    if (scheduleId !== undefined) {
      if (existing.data === undefined) {
        return;
      }
      setMode(openExisting(existing.data.schedule.cron));
      return;
    }
    const recurrence = applyPreset("daily09");
    if (recurrence !== null) {
      setMode({ raw: false, recurrence });
    }
  }, [existing.data, mode, scheduleId]);

  useEffect(() => {
    if (timezone !== null) {
      return;
    }
    if (scheduleId !== undefined) {
      if (existing.data === undefined) {
        return;
      }
      setTimezone(existing.data.schedule.timezone);
      return;
    }
    if (instance.data == null) {
      return;
    }
    const known = Intl.supportedValuesOf("timeZone");
    setTimezone(
      defaultTimezone(
        Intl.DateTimeFormat().resolvedOptions().timeZone,
        known,
        instance.data.default_timezone,
      ),
    );
  }, [existing.data, instance.data, scheduleId, timezone]);

  useEffect(() => {
    if (document.data === undefined || rows !== null) {
      return;
    }
    if (scheduleId !== undefined) {
      if (existing.data === undefined) {
        return;
      }
      setRows(
        applyCopiedBatch(columnsOf(document.data.variables ?? []), [
          { variables: existing.data.schedule.variables },
        ]),
      );
      setName(existing.data.schedule.name ?? "");
      setEnabled(existing.data.schedule.enabled);
      return;
    }
    setRows(initialRows(document.data.variables ?? [], 1));
  }, [document.data, existing.data, rows, scheduleId]);

  const cron = mode === null ? "" : cronOf(mode);
  const preview = useQuery(schedulePreviewQuery(orgId, cron, timezone ?? ""));

  const save = useMutation({
    mutationFn: async (body: CreateSchedule) => {
      if (scheduleId === undefined) {
        const { data, error } = await createSchedule({
          path: { workflow_id: workflowId },
          body,
        });
        if (error) throw error;
        return data;
      }
      const { data, error } = await updateSchedule({
        path: { schedule_id: scheduleId },
        body,
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      router.push(schedulesHref(workflowId));
    },
  });

  if (workflow.error) {
    return <Callout tone="bad">{refusalMessage(workflow.error)}</Callout>;
  }
  if (document.error) {
    return <Callout tone="bad">{refusalMessage(document.error)}</Callout>;
  }
  if (existing.error) {
    return <Callout tone="bad">{refusalMessage(existing.error)}</Callout>;
  }
  if (published === null && workflow.data !== undefined) {
    return <Callout tone="bad">{COPY.noPublishedVersion}</Callout>;
  }
  if (
    workflow.data === undefined ||
    document.data === undefined ||
    mode === null ||
    timezone === null ||
    rows === null
  ) {
    return null;
  }

  const readback = humanize(cron);
  const missing = emptyVariableNames(rows[0] ?? {}, columns);
  const lastRun = lastNonTestVariables(runs.data ?? []);
  const viewerTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const zones = zoneOptions(timezone);
  const refused = save.error;
  const emptyNote = attempted && missing.length > 0 ? emptyValueMessage(missing) : null;

  const submit = () => {
    setAttempted(true);
    if (missing.length > 0) {
      return;
    }
    save.mutate(
      scheduleBody({
        cron,
        timezone,
        enabled,
        variables: submittedVariables(rows[0] ?? {}, columns),
        name,
      }),
    );
  };

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-title font-semibold">
        {scheduleId === undefined ? "New schedule" : "Edit schedule"}
      </h2>

      {refused ? <Callout tone="bad">{refusalMessage(refused)}</Callout> : null}
      {emptyNote ? <Callout tone="bad">{emptyNote}</Callout> : null}

      <div className="flex flex-wrap gap-1.5">
        {PRESETS.map((preset) => {
          const on = !mode.raw && cronOf({ raw: false, recurrence: preset.recurrence }) === cron;
          return (
            <Button
              key={preset.id}
              type="button"
              size="sm"
              variant={on ? "default" : "secondary"}
              className="rounded-full"
              onClick={() => {
                setMode({ raw: false, recurrence: preset.recurrence });
              }}
            >
              {preset.label}
            </Button>
          );
        })}
      </div>

      {mode.raw ? (
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-half text-mut">
            cron
            <Input
              aria-label="cron"
              value={mode.cron}
              className="h-8 w-56 font-mono text-half"
              onChange={(typed) => {
                setMode(writeCronInstead(typed.target.value));
              }}
            />
          </label>
          {openExisting(mode.cron).raw === false ? (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => {
                setMode(openExisting(mode.cron));
              }}
            >
              back to the sentence
            </Button>
          ) : null}
        </div>
      ) : (
        <Sentence
          workflowName={workflow.data.name}
          recurrence={mode.recurrence}
          timezone={timezone}
          zones={zones}
          onRecurrence={(recurrence) => {
            setMode({ raw: false, recurrence });
          }}
          onTimezone={setTimezone}
        />
      )}

      <p className="font-mono text-small text-mut">
        {cron}
        {mode.raw ? null : (
          <>
            {" · "}
            <button
              type="button"
              className="text-accent hover:underline"
              onClick={() => {
                setMode(writeCronInstead(cron));
              }}
            >
              write cron instead
            </button>
          </>
        )}
      </p>

      {mode.raw ? (
        <label className="flex items-center gap-2 text-half text-mut">
          Timezone
          <TimezoneSelect value={timezone} zones={zones} onChange={setTimezone} />
        </label>
      ) : null}

      <div className="flex flex-col gap-1">
        {readback === null ? (
          <p className="text-half text-wait">{cron}</p>
        ) : (
          <p className="text-title font-semibold">{readback}</p>
        )}
        {preview.error ? <Callout tone="bad">{refusalMessage(preview.error)}</Callout> : null}
        {preview.data === undefined ? null : (
          <ol className="text-half">
            {preview.data.map((iso) => {
              const shown = occurrenceLabel(iso, timezone, viewerTz);
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

      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-micro font-semibold tracking-wide text-mut uppercase">Values</h3>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            className="ml-auto"
            disabled={lastRun === null}
            onClick={() => {
              if (lastRun === null) {
                return;
              }
              setRows(applyCopiedBatch(columns, [{ variables: lastRun }]));
            }}
          >
            Fill from my last Run
          </Button>
        </div>
        <ValueGrid variables={variables} rows={rows} onChange={setRows} fixedRowCount={1} />
      </div>

      <StickyActionFooter className="flex-wrap justify-between gap-3">
        <div className="mr-auto flex min-w-0 flex-1 flex-col gap-2">
          <label className="flex min-w-0 items-center gap-2 text-small text-mut">
            Name
            <Input
              aria-label="Schedule name"
              value={name}
              placeholder="Optional"
              className="h-7 max-w-md text-half"
              onChange={(typed) => {
                setName(typed.target.value);
              }}
            />
          </label>
          <label className="flex items-center gap-2 text-half text-ink">
            <input
              type="checkbox"
              className="size-4 accent-accent"
              checked={enabled}
              onChange={(ticked) => {
                setEnabled(ticked.target.checked);
              }}
            />
            Enabled
          </label>
        </div>
        <Button disabled={save.isPending} onClick={submit}>
          {scheduleId === undefined ? "Create schedule" : "Save schedule"}
        </Button>
      </StickyActionFooter>
    </div>
  );
}

function Sentence({
  workflowName,
  recurrence,
  timezone,
  zones,
  onRecurrence,
  onTimezone,
}: {
  workflowName: string;
  recurrence: Recurrence;
  timezone: string;
  zones: readonly string[];
  onRecurrence: (recurrence: Recurrence) => void;
  onTimezone: (timezone: string) => void;
}) {
  const needsClock = recurrence.kind !== "everyNMinutes";

  return (
    <div className="flex flex-wrap items-center gap-2 text-title">
      <span className="text-mut">Run</span>
      <span className="font-semibold">{workflowName}</span>
      <select
        aria-label="frequency"
        className="h-8 rounded-md border border-line bg-panel px-2 text-half text-ink"
        value={recurrence.kind}
        onChange={(chosen) => {
          onRecurrence(withFrequency(recurrence, chosen.target.value as Recurrence["kind"]));
        }}
      >
        {FREQUENCY_OPTIONS.map((option) => (
          <option key={option.kind} value={option.kind}>
            {option.label}
          </option>
        ))}
      </select>
      {recurrence.kind === "everyNMinutes" ? (
        <>
          <span className="text-mut">every</span>
          <select
            aria-label="minute interval"
            className="h-8 rounded-md border border-line bg-panel px-2 text-half text-ink"
            value={recurrence.n}
            onChange={(chosen) => {
              onRecurrence({ kind: "everyNMinutes", n: Number(chosen.target.value) });
            }}
          >
            {MINUTE_INTERVALS.map((n) => (
              <option key={n} value={n}>
                {String(n)}
              </option>
            ))}
          </select>
          <span className="text-mut">minutes</span>
        </>
      ) : null}
      {recurrence.kind === "weekly" ? (
        <>
          <span className="text-mut">on</span>
          <select
            aria-label="weekday"
            className="h-8 rounded-md border border-line bg-panel px-2 text-half text-ink"
            value={recurrence.weekdays[0] ?? 1}
            onChange={(chosen) => {
              onRecurrence({
                ...recurrence,
                weekdays: [Number(chosen.target.value)],
              });
            }}
          >
            {WEEKDAY_OPTIONS.map((day) => (
              <option key={day.value} value={day.value}>
                {day.label}
              </option>
            ))}
          </select>
        </>
      ) : null}
      {recurrence.kind === "monthly" ? (
        <>
          <span className="text-mut">on day</span>
          <select
            aria-label="day of month"
            className="h-8 rounded-md border border-line bg-panel px-2 text-half text-ink"
            value={recurrence.day}
            onChange={(chosen) => {
              onRecurrence({ ...recurrence, day: Number(chosen.target.value) });
            }}
          >
            {Array.from({ length: 31 }, (_, index) => index + 1).map((day) => (
              <option key={day} value={day}>
                {String(day)}
              </option>
            ))}
          </select>
        </>
      ) : null}
      {needsClock ? (
        <>
          <span className="text-mut">at</span>
          <Input
            type="time"
            aria-label="time"
            value={clockValue(recurrence)}
            className="h-8 w-28 text-half"
            onChange={(typed) => {
              const [hour, minute] = typed.target.value.split(":").map(Number);
              onRecurrence(withClock(recurrence, hour ?? 0, minute ?? 0));
            }}
          />
        </>
      ) : null}
      <span className="text-mut">in</span>
      <TimezoneSelect value={timezone} zones={zones} onChange={onTimezone} />
    </div>
  );
}

function TimezoneSelect({
  value,
  zones,
  onChange,
}: {
  value: string;
  zones: readonly string[];
  onChange: (timezone: string) => void;
}) {
  return (
    <select
      aria-label="timezone"
      className="h-8 max-w-xs rounded-md border border-line bg-panel px-2 text-half text-ink"
      value={value}
      onChange={(chosen) => {
        onChange(chosen.target.value);
      }}
    >
      {zones.map((zone) => (
        <option key={zone} value={zone}>
          {zone}
        </option>
      ))}
    </select>
  );
}

function zoneOptions(current: string): string[] {
  const known = Intl.supportedValuesOf("timeZone");
  return known.includes(current) ? known : [current, ...known];
}
