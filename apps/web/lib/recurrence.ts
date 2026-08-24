export type Recurrence =
  | { kind: "everyNMinutes"; n: number }
  | { kind: "hourly"; minute: number }
  | { kind: "daily"; hour: number; minute: number }
  | { kind: "weekdays"; hour: number; minute: number }
  | { kind: "weekly"; weekdays: number[]; hour: number; minute: number }
  | { kind: "monthly"; day: number; hour: number; minute: number };

const WEEKDAY_NAMES = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
] as const;

function inRange(value: number, minimum: number, maximum: number): boolean {
  return Number.isInteger(value) && value >= minimum && value <= maximum;
}

function requireRange(value: number, minimum: number, maximum: number, field: string): void {
  if (!inRange(value, minimum, maximum)) {
    throw new RangeError(`${field} must be a whole number from ${minimum} to ${maximum}`);
  }
}

function requireTime(hour: number, minute: number): void {
  requireRange(hour, 0, 23, "hour");
  requireRange(minute, 0, 59, "minute");
}

export function toCron(recurrence: Recurrence): string {
  switch (recurrence.kind) {
    case "everyNMinutes":
      requireRange(recurrence.n, 1, 59, "minute interval");
      return `*/${recurrence.n} * * * *`;
    case "hourly":
      requireRange(recurrence.minute, 0, 59, "minute");
      return `${recurrence.minute} * * * *`;
    case "daily":
      requireTime(recurrence.hour, recurrence.minute);
      return `${recurrence.minute} ${recurrence.hour} * * *`;
    case "weekdays":
      requireTime(recurrence.hour, recurrence.minute);
      return `${recurrence.minute} ${recurrence.hour} * * 1-5`;
    case "weekly": {
      requireTime(recurrence.hour, recurrence.minute);
      if (
        recurrence.weekdays.length === 0 ||
        new Set(recurrence.weekdays).size !== recurrence.weekdays.length
      ) {
        throw new RangeError("weekdays must contain distinct days");
      }
      for (const weekday of recurrence.weekdays) {
        requireRange(weekday, 0, 6, "weekday");
      }
      return `${recurrence.minute} ${recurrence.hour} * * ${recurrence.weekdays.join(",")}`;
    }
    case "monthly":
      requireTime(recurrence.hour, recurrence.minute);
      requireRange(recurrence.day, 1, 31, "day");
      return `${recurrence.minute} ${recurrence.hour} ${recurrence.day} * *`;
  }
}

function parseNumber(field: string, minimum: number, maximum: number): number | null {
  if (!/^\d+$/.test(field)) {
    return null;
  }
  const value = Number(field);
  return inRange(value, minimum, maximum) ? value : null;
}

export function fromCron(cron: string): Recurrence | null {
  const fields = cron.trim().split(/\s+/);
  if (fields.length !== 5) {
    return null;
  }

  const [minuteField, hourField, dayField, monthField, weekdayField] = fields;
  if (
    minuteField === undefined ||
    hourField === undefined ||
    dayField === undefined ||
    monthField === undefined ||
    weekdayField === undefined ||
    monthField !== "*"
  ) {
    return null;
  }

  const intervalMatch = /^\*\/(\d+)$/.exec(minuteField);
  if (intervalMatch !== null && hourField === "*" && dayField === "*" && weekdayField === "*") {
    const n = parseNumber(intervalMatch[1] ?? "", 1, 59);
    return n === null ? null : { kind: "everyNMinutes", n };
  }

  const minute = parseNumber(minuteField, 0, 59);
  if (minute === null) {
    return null;
  }

  if (hourField === "*" && dayField === "*" && weekdayField === "*") {
    return { kind: "hourly", minute };
  }

  const hour = parseNumber(hourField, 0, 23);
  if (hour === null) {
    return null;
  }

  if (dayField === "*" && weekdayField === "*") {
    return { kind: "daily", hour, minute };
  }
  if (dayField === "*" && weekdayField === "1-5") {
    return { kind: "weekdays", hour, minute };
  }
  if (dayField === "*" && /^(?:[0-6])(?:,[0-6])*$/.test(weekdayField)) {
    const weekdays = weekdayField.split(",").map(Number);
    if (new Set(weekdays).size !== weekdays.length) {
      return null;
    }
    return { kind: "weekly", weekdays, hour, minute };
  }
  if (weekdayField === "*") {
    const day = parseNumber(dayField, 1, 31);
    return day === null ? null : { kind: "monthly", day, hour, minute };
  }

  return null;
}

function time(hour: number, minute: number): string {
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function list(items: string[]): string {
  if (items.length < 2) {
    return items[0] ?? "";
  }
  return `${items.slice(0, -1).join(", ")} and ${items.at(-1)}`;
}

function weekdayName(day: number): string {
  const name = WEEKDAY_NAMES[day];
  if (name === undefined) {
    throw new RangeError("weekday must be from 0 to 6");
  }
  return name;
}

export function humanize(cron: string): string | null {
  const recurrence = fromCron(cron);
  if (recurrence === null) {
    return null;
  }

  switch (recurrence.kind) {
    case "everyNMinutes":
      return `every ${recurrence.n} minutes`;
    case "hourly":
      return `every hour at :${String(recurrence.minute).padStart(2, "0")}`;
    case "daily":
      return `every day at ${time(recurrence.hour, recurrence.minute)}`;
    case "weekdays":
      return `every weekday at ${time(recurrence.hour, recurrence.minute)}`;
    case "weekly":
      return `every ${list(recurrence.weekdays.map(weekdayName))} at ${time(recurrence.hour, recurrence.minute)}`;
    case "monthly":
      return `every month on day ${recurrence.day} at ${time(recurrence.hour, recurrence.minute)}`;
  }
}
