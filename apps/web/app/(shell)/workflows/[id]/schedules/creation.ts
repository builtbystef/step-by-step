import type { CreateSchedule, RunTrigger } from "@step-by-step/api-client";

import type { GridColumn, GridRow } from "../../../../../components/value-grid/grid";
import { fromCron, toCron, type Recurrence } from "../../../../../lib/recurrence";

/**
 * The Schedule creation page's decisions: the preset chips, the sentence ↔
 * cron mode, the preview request, the timezone default, fill-from-last-Run,
 * the empty-value refusal, and the save payload.
 *
 * The page draws these. It does not re-decide them. Occurrence *times* come
 * from the preview endpoint; this module only phrases the timestamps it is
 * given.
 */

export type RecurrenceMode = { raw: false; recurrence: Recurrence } | { raw: true; cron: string };

export type PresetId =
  | "hourly"
  | "every15"
  | "daily09"
  | "weekdays09"
  | "mondays0730"
  | "firstOfMonth";

export const PRESETS: readonly { id: PresetId; label: string; recurrence: Recurrence }[] = [
  { id: "hourly", label: "hourly", recurrence: { kind: "hourly", minute: 0 } },
  { id: "every15", label: "every 15 min", recurrence: { kind: "everyNMinutes", n: 15 } },
  { id: "daily09", label: "daily 09:00", recurrence: { kind: "daily", hour: 9, minute: 0 } },
  {
    id: "weekdays09",
    label: "weekdays 09:00",
    recurrence: { kind: "weekdays", hour: 9, minute: 0 },
  },
  {
    id: "mondays0730",
    label: "Mondays 07:30",
    recurrence: { kind: "weekly", weekdays: [1], hour: 7, minute: 30 },
  },
  {
    id: "firstOfMonth",
    label: "1st of month",
    recurrence: { kind: "monthly", day: 1, hour: 0, minute: 0 },
  },
];

export function applyPreset(id: string): Recurrence | null {
  return PRESETS.find((preset) => preset.id === id)?.recurrence ?? null;
}

export function cronOf(mode: RecurrenceMode): string {
  return mode.raw ? mode.cron : toCron(mode.recurrence);
}

export function writeCronInstead(cron: string): RecurrenceMode {
  return { raw: true, cron };
}

export function openExisting(cron: string): RecurrenceMode {
  const recurrence = fromCron(cron);
  return recurrence === null ? { raw: true, cron } : { raw: false, recurrence };
}

export function previewBody(cron: string, timezone: string): { cron: string; timezone: string } {
  return { cron, timezone };
}

/**
 * The picker default: the browser's IANA zone when the instance knows it,
 * else the instance default (UTC unless DEFAULT_TIMEZONE says otherwise).
 */
export function defaultTimezone(
  browserZone: string | undefined,
  knownZones: readonly string[],
  instanceDefault: string,
): string {
  if (browserZone !== undefined && knownZones.includes(browserZone)) {
    return browserZone;
  }
  return instanceDefault;
}

const OCCURRENCE_FORMAT: Intl.DateTimeFormatOptions = {
  weekday: "short",
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
};

export function occurrenceLabel(
  iso: string,
  scheduleTz: string,
  viewerTz: string,
): { at: string; local: string | null } {
  const at = formatInZone(iso, scheduleTz);
  return { at, local: scheduleTz === viewerTz ? null : formatInZone(iso, viewerTz) };
}

function formatInZone(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-GB", { ...OCCURRENCE_FORMAT, timeZone }).format(new Date(iso));
}

export function lastNonTestVariables(
  runs: readonly { trigger: RunTrigger; variables?: Record<string, unknown> }[],
): Record<string, unknown> | null {
  const run = runs.find((entry) => entry.trigger !== "test");
  return run?.variables ?? null;
}

export function emptyVariableNames(row: GridRow, columns: readonly GridColumn[]): string[] {
  return columns
    .filter((column) => !column.secret && (row[column.name] ?? "").trim() === "")
    .map((column) => column.name);
}

export function scheduleBody(asked: {
  cron: string;
  timezone: string;
  enabled: boolean;
  variables: Record<string, string>;
  name: string;
}): CreateSchedule {
  const name = asked.name.trim();
  return {
    cron: asked.cron,
    timezone: asked.timezone,
    enabled: asked.enabled,
    variables: asked.variables,
    name: name === "" ? null : name,
  };
}

export function schedulesHref(workflowId: string): string {
  return `/workflows/${workflowId}/schedules`;
}

export const FREQUENCY_OPTIONS: readonly { kind: Recurrence["kind"]; label: string }[] = [
  { kind: "everyNMinutes", label: "every few minutes" },
  { kind: "hourly", label: "every hour" },
  { kind: "daily", label: "every day" },
  { kind: "weekdays", label: "every weekday" },
  { kind: "weekly", label: "every week" },
  { kind: "monthly", label: "every month" },
];

export const WEEKDAY_OPTIONS: readonly { value: number; label: string }[] = [
  { value: 0, label: "Sunday" },
  { value: 1, label: "Monday" },
  { value: 2, label: "Tuesday" },
  { value: 3, label: "Wednesday" },
  { value: 4, label: "Thursday" },
  { value: 5, label: "Friday" },
  { value: 6, label: "Saturday" },
];

export const MINUTE_INTERVALS = [5, 10, 15, 20, 30] as const;

function clockOf(recurrence: Recurrence): { hour: number; minute: number } {
  switch (recurrence.kind) {
    case "everyNMinutes":
      return { hour: 9, minute: 0 };
    case "hourly":
      return { hour: 0, minute: recurrence.minute };
    default:
      return { hour: recurrence.hour, minute: recurrence.minute };
  }
}

/** Keep the clock (and interval / day) when the sentence's frequency changes. */
export function withFrequency(current: Recurrence, kind: Recurrence["kind"]): Recurrence {
  const { hour, minute } = clockOf(current);
  switch (kind) {
    case "everyNMinutes":
      return {
        kind,
        n: current.kind === "everyNMinutes" ? current.n : 15,
      };
    case "hourly":
      return { kind, minute };
    case "daily":
      return { kind, hour, minute };
    case "weekdays":
      return { kind, hour, minute };
    case "weekly":
      return {
        kind,
        weekdays: current.kind === "weekly" ? current.weekdays : [1],
        hour,
        minute,
      };
    case "monthly":
      return {
        kind,
        day: current.kind === "monthly" ? current.day : 1,
        hour,
        minute,
      };
  }
}

export function clockValue(recurrence: Recurrence): string {
  const { hour, minute } = clockOf(recurrence);
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

export function withClock(current: Recurrence, hour: number, minute: number): Recurrence {
  switch (current.kind) {
    case "everyNMinutes":
      return current;
    case "hourly":
      return { kind: "hourly", minute };
    case "daily":
    case "weekdays":
      return { ...current, hour, minute };
    case "weekly":
      return { ...current, hour, minute };
    case "monthly":
      return { ...current, hour, minute };
  }
}
