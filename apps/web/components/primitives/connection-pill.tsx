import { connectionLabel, type ConnectionState } from "@/lib/labels";
import { cn } from "@/lib/utils";

const STATE_CLASSES: Record<ConnectionState, string> = {
  connected: "bg-ok-bg text-ok",
  not_connected: "bg-muted text-muted-foreground",
  out_of_date: "bg-wait-bg text-wait",
};

/**
 * The extension's connection state, in the sidebar footer.
 *
 * Three states, not four: "not installed" and "installed but not pointed at
 * this instance" are indistinguishable from the app's side, so they are one
 * state with one recovery path rather than a guess.
 *
 * Pure over props here: the handshake probe arrives with the slice that wires
 * the sidebar.
 */
export function ConnectionPill({
  state,
  version,
  className,
}: {
  state: ConnectionState;
  version?: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-small font-semibold",
        STATE_CLASSES[state],
        className,
      )}
    >
      <span aria-hidden className="size-1.5 rounded-full bg-current" />
      {connectionLabel(state)}
      {version ? <span className="font-normal">· v{version}</span> : null}
    </span>
  );
}
