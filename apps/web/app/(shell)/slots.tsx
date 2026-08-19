import { CountBadge } from "@/components/primitives/count-badge";

/**
 * The three places in the shell that a later slice fills.
 *
 * They are components rather than gaps in the markup so that the seam is a
 * real one: the slice that arrives replaces the body of the function it owns,
 * and nothing about the shell around it has to move.
 */

/**
 * Above the page title, spanning the content column: where the attention band
 * renders when a Run is waiting on the person reading the screen.
 *
 * `fkgat7` brings `GET /api/attention`, the poll, and the countdown; until it
 * does there is nothing to say, and a band with nothing to say is worse than
 * no band.
 */
export function AttentionSlot() {
  return null;
}

/**
 * On the Runs nav item: how many Runs are in flight or waiting.
 *
 * `fkgat7` feeds it from the same poll as the band. A `CountBadge` is hidden
 * at zero, so the slot is honest before then rather than empty-looking — and
 * it keeps its place in the icon rail, where the label is gone but the number
 * is the whole point.
 */
export function RunsCountSlot() {
  return <CountBadge count={0} tone="in-flight" />;
}

/**
 * In the sidebar footer, beside the user menu: the extension's connection
 * state.
 *
 * `20k5ft` brings the handshake probe, the version comparison, and the
 * `/settings/extension` surface behind it. "Not connected" is a real state and
 * not a default, so nothing is shown until something has actually probed.
 */
export function ConnectionPillSlot() {
  return null;
}
