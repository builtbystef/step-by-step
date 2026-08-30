const FORMAT = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 24 * 60 * 60],
  ["month", 30 * 24 * 60 * 60],
  ["day", 24 * 60 * 60],
  ["hour", 60 * 60],
  ["minute", 60],
  ["second", 1],
];

const JUST_NOW_SECONDS = 10;

export function relativeTime(when: string, now: Date = new Date()): string {
  const seconds = (now.getTime() - new Date(when).getTime()) / 1000;
  if (seconds < JUST_NOW_SECONDS) {
    return "just now";
  }
  for (const [unit, length] of UNITS) {
    const count = Math.floor(seconds / length);
    if (count >= 1) {
      return FORMAT.format(-count, unit);
    }
  }
  return "just now";
}
