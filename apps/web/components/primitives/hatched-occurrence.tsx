import { cn } from "@/lib/utils";

/**
 * A slot in a Schedule's Occurrence strip where nothing happens. A 3px hatch,
 * in one of four readings:
 *
 * - `prevented` — amber, 45°: overlap. A human should look.
 * - `missed` — grey, 135°: the instance was not running; never run late.
 * - `missing-values` — red, 45°: the Workflow now declares a Variable this
 *   Schedule has no value for.
 * - `never-due` — grey, 45°: the Schedule was never due here (a paused band),
 *   so nothing is wrong.
 */
export type OccurrenceHatch = "prevented" | "missed" | "missing-values" | "never-due";

const HATCH_CLASSES: Record<OccurrenceHatch, string> = {
  prevented:
    "border-wait/30 bg-[repeating-linear-gradient(45deg,transparent_0_3px,var(--wait)_3px_6px)]",
  missed:
    "border-line bg-[repeating-linear-gradient(135deg,transparent_0_3px,var(--line)_3px_6px)]",
  "missing-values":
    "border-bad/30 bg-[repeating-linear-gradient(45deg,transparent_0_3px,var(--bad)_3px_6px)]",
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
