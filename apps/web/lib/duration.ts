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

function trimmed(seconds: number): string {
  return String(Math.round(seconds * 10) / 10);
}
