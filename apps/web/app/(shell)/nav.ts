import { CalendarClock, PlayCircle, Settings, Workflow, type LucideIcon } from "lucide-react";

export type Destination = {
  label: string;
  path: string;
  icon: LucideIcon;
};

export const NAV_DESTINATIONS: readonly Destination[] = [
  { label: "Workflows", path: "/workflows", icon: Workflow },
  { label: "Runs", path: "/runs", icon: PlayCircle },
  { label: "Schedules", path: "/schedules", icon: CalendarClock },
];

export const SETTINGS_DESTINATION: Destination = {
  label: "Settings",
  path: "/settings",
  icon: Settings,
};

export function isCurrentSection(pathname: string, destination: string): boolean {
  const path = pathname.split("?")[0] ?? "";
  return path === destination || path.startsWith(`${destination}/`);
}
