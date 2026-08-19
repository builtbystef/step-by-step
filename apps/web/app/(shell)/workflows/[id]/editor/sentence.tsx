import type { Segment } from "./summary";

import { cn } from "@/lib/utils";

/**
 * The card's summary line: the Step as words, with the two things that are
 * not words drawn as themselves.
 *
 * A Variable is a pill in the human hue — it is a value a person supplies —
 * and the element is a token. A token that came from a selector rather than
 * from something the page says out loud is monospace, because that is what it
 * is: a machine string.
 *
 * The parts are keyed by position: a sentence is derived from the Step on
 * every render, so no part of it has an identity of its own.
 */
export function Sentence({ segments }: { segments: Segment[] }) {
  return (
    <span className="text-half text-mut">
      {segments.map((part, at) => {
        if (part.kind === "text") {
          return <span key={at}>{part.text}</span>;
        }
        if (part.kind === "variable") {
          return (
            <span key={at} className="rounded bg-human-bg px-1 font-semibold text-human">
              {`{{${part.name}}}`}
            </span>
          );
        }
        return (
          <span
            key={at}
            className={cn("rounded bg-muted px-1 text-ink", part.machine && "font-mono text-small")}
          >
            {part.text}
          </span>
        );
      })}
    </span>
  );
}
