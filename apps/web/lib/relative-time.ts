/**
 * How long ago something happened, in words.
 *
 * `Intl.RelativeTimeFormat` rather than a date library: the app renders "2h
 * ago" and a Schedule's own timezone, and the platform does both. The decision
 * that is this module's is the unit — the coarsest one that still says
 * something, because a list of times reads as a shape and "4200 seconds ago"
 * has none.
 */

const FORMAT = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

/** How long the units are, largest first. The first one that fits is used. */
const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 24 * 60 * 60],
  ["month", 30 * 24 * 60 * 60],
  ["day", 24 * 60 * 60],
  ["hour", 60 * 60],
  ["minute", 60],
  ["second", 1],
];

/**
 * Under this, nothing is counted at all.
 *
 * It also absorbs a browser clock running a little ahead of the server's: a
 * timestamp a few seconds in the future is this moment, not a future the app
 * would otherwise render as "in 3 seconds".
 */
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
