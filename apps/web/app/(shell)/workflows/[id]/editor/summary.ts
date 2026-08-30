import type { Target } from "@step-by-step/api-client";

import { targetsOf, type Step } from "./steps";
import { REFERENCE } from "./variables";

import { duration } from "../../../../../lib/duration";

export type Segment =
  | { kind: "text"; text: string }
  | { kind: "variable"; name: string }
  | { kind: "target"; text: string; machine: boolean };

export function summarize(step: Step): Segment[] {
  const [target] = targetsOf(step);
  const element = target ? { ...targetToken(target), kind: "target" as const } : null;
  switch (step.type) {
    case "navigate":
      return joined([text("Go to "), ...interpolated(step.payload.url)]);
    case "click":
      return joined([text("Click "), element]);
    case "type":
      return joined([text("Type "), ...interpolated(step.payload.value), text(" into "), element]);
    case "select":
      return joined([text(`Choose ${step.payload.value} in `), element]);
    case "download":
      return joined([text("Download the file from "), element]);
    case "extract":
      return joined([
        text(`Extract ${listed(step.payload.mode)}${step.payload.outputName} from `),
        element,
        step.payload.mode === "scalar" && step.payload.attribute !== undefined
          ? text(`, its ${step.payload.attribute} attribute`)
          : null,
      ]);
    case "wait":
      return step.payload.mode === "duration"
        ? joined([text(`Wait ${duration(step.payload.durationMs)}`)])
        : joined([text("Wait for "), element, text(" to appear")]);
    case "pause-for-takeover":
      return joined([
        text(
          step.payload.message === undefined || step.payload.message === ""
            ? "Pause for a person to take over"
            : `Pause and ask: “${step.payload.message}”`,
        ),
      ]);
  }
}

export function sentenceOf(step: Step): string {
  return summarize(step)
    .map((part) => (part.kind === "variable" ? `{{${part.name}}}` : part.text))
    .join("");
}

export function targetToken(target: Target): { text: string; machine: boolean } {
  const spoken = target.candidates.find((candidate) => candidate.kind !== "css");
  if (spoken) {
    return { text: spoken.value, machine: false };
  }
  const [first] = target.candidates;
  return first ? { text: first.value, machine: true } : { text: "the element", machine: false };
}

function text(said: string): Segment {
  return { kind: "text", text: said };
}

function listed(mode: "scalar" | "list"): string {
  return mode === "list" ? "a list of " : "";
}

function interpolated(value: string): Segment[] {
  const parts: Segment[] = [];
  let read = 0;
  for (const found of value.matchAll(REFERENCE)) {
    const name = found[1];
    if (name === undefined) {
      continue;
    }
    if (found.index > read) {
      parts.push(text(value.slice(read, found.index)));
    }
    parts.push({ kind: "variable", name });
    read = found.index + found[0].length;
  }
  if (read < value.length) {
    parts.push(text(value.slice(read)));
  }
  return parts;
}

function joined(parts: (Segment | null)[]): Segment[] {
  const sentence: Segment[] = [];
  for (const part of parts) {
    if (part === null || (part.kind === "text" && part.text === "")) {
      continue;
    }
    const last = sentence.at(-1);
    if (last?.kind === "text" && part.kind === "text") {
      sentence[sentence.length - 1] = text(last.text + part.text);
    } else {
      sentence.push(part);
    }
  }
  return sentence;
}
