import { cn } from "@/lib/utils";

/**
 * A slot in a Schedule's Occurrence strip where nothing happens. A 45° 3px
 * hatch, in one of two readings:
 *
 * - `prevented` — amber: the Occurrence was due and something stopped it
 *   (`overlap`, `missing_values`). Amber, because a human should look.
 * - `never-due` — grey: the Schedule was never due here, so nothing is wrong.
 */
export type OccurrenceHatch = "prevented" | "never-due";

const HATCH_CLASSES: Record<OccurrenceHatch, string> = {
  prevented:
    "border-wait/30 bg-[repeating-linear-gradient(45deg,transparent_0_3px,var(--wait)_3px_6px)]",
  "never-due":
    "border-line bg-[repeating-linear-gradient(45deg,transparent_0_3px,var(--line)_3px_6px)]",
};

export function HatchedOccurrence({
  kind,
  label,
  className,
}: {
  kind: OccurrenceHatch;
  label: string;
  className?: string;
}) {
  return (
    <span
      role="img"
      title={label}
      aria-label={label}
      className={cn("inline-block h-5 w-3 rounded-sm border", HATCH_CLASSES[kind], className)}
    />
  );
}
