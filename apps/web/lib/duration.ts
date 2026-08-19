/**
 * How long something takes, in the words a person reads.
 *
 * The document stores every length as milliseconds, because that is what
 * Playwright waits in. Nobody reads a Step as waiting 90000 of anything, so
 * every screen that shows one of those numbers comes through here — and the
 * Step's timeout, the workflow default under an empty timeout field, and a
 * wait Step's own duration are then the same sentence in three places.
 */

const SECOND = 1000;
const MINUTE = 60 * SECOND;

export function duration(ms: number): string {
  if (ms < SECOND) {
    return `${String(ms)} ms`;
  }
  if (ms < MINUTE) {
    return `${trimmed(ms / SECOND)} s`;
  }
  const minutes = Math.floor(ms / MINUTE);
  const seconds = trimmed((ms - minutes * MINUTE) / SECOND);
  return seconds === "0" ? `${String(minutes)} min` : `${String(minutes)} min ${seconds} s`;
}

/**
 * One decimal, and none at all when it would be a nought: 1.5 s says
 * something 1 s does not, and 5.0 s says nothing 5 s does not.
 */
function trimmed(seconds: number): string {
  return String(Math.round(seconds * 10) / 10);
}
