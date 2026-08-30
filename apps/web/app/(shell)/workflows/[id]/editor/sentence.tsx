import { KeyRound } from "lucide-react";

import type { Segment } from "./summary";

import { cn } from "@/lib/utils";

export function Sentence({
  segments,
  secrets,
}: {
  segments: Segment[];
  secrets: ReadonlySet<string>;
}) {
  return (
    <span className="text-half text-mut">
      {segments.map((part, at) => {
        if (part.kind === "text") {
          return <span key={at}>{part.text}</span>;
        }
        if (part.kind === "variable") {
          return secrets.has(part.name) ? (
            <span
              key={at}
              className="inline-flex items-center gap-0.5 rounded bg-human px-1 font-semibold text-panel"
            >
              <KeyRound className="size-3" />
              {`{{${part.name}}}`}
            </span>
          ) : (
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
