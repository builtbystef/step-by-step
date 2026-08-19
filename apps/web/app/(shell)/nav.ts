import { CalendarClock, PlayCircle, Settings, Workflow, type LucideIcon } from "lucide-react";

/**
 * What the sidebar's nav offers, and which item an address lights up.
 *
 * Kept beside the sidebar rather than inside it so that the order and the
 * highlighting rule are read back directly: they are decisions, and a JSX file
 * is a poor place to keep a decision.
 */

export type Destination = {
  label: string;
  path: string;
  icon: LucideIcon;
};

/** The work itself, above the separator. */
export const NAV_DESTINATIONS: readonly Destination[] = [
  { label: "Workflows", path: "/workflows", icon: Workflow },
  { label: "Runs", path: "/runs", icon: PlayCircle },
  { label: "Schedules", path: "/schedules", icon: CalendarClock },
];

/**
 * Settings, below the separator. It is not one of the three: it is where the
 * instance is configured rather than where the work is done, and the separator
 * is what says so.
 */
export const SETTINGS_DESTINATION: Destination = {
  label: "Settings",
  path: "/settings",
  icon: Settings,
};

/**
 * Whether an address belongs to a destination.
 *
 * A section owns everything beneath it — a Run detail is still Runs, and a
 * Settings panel is still Settings — but only at a segment boundary, so that
 * `/schedules-archive` is not `/schedules` wearing a longer name. The query is
 * a filter rather than a place, and it does not enter into it.
 */
export function isCurrentSection(pathname: string, destination: string): boolean {
  const path = pathname.split("?")[0] ?? "";
  return path === destination || path.startsWith(`${destination}/`);
}
