import type { Target } from "@step-by-step/api-client";

import { targetsOf, type Step } from "./steps";

import { duration } from "../../../../../lib/duration";

/**
 * A Step as the sentence its card reads.
 *
 * The prototype settled this: cards scale to a long recording and carry the
 * envelope, sentences win comprehension, and the hybrid keeps both — so the
 * line under the label is the Step in words. It comes out in parts rather
 * than as a string, because two of those parts are not words: a Variable is a
 * pill and the element is a token, and a card that had to find the braces
 * again to draw them would be reading the same value twice.
 */

export type Segment =
  | { kind: "text"; text: string }
  | { kind: "variable"; name: string }
  | { kind: "target"; text: string; machine: boolean };

const REFERENCE = /\{\{\s*([A-Za-z_][A-Za-z0-9_-]*)\s*\}\}/g;
/** A Variable reference, as the document store reads one when it validates. */

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

/** The same sentence as one string — what a test reads, and a title attribute. */
export function sentenceOf(step: Step): string {
  return summarize(step)
    .map((part) => (part.kind === "variable" ? `{{${part.name}}}` : part.text))
    .join("");
}

/**
 * What to call the element in the sentence.
 *
 * The candidates are ranked best-first for replay, and the best one for
 * replay is not always the one a person recognises: a CSS candidate is a
 * position on the page, and a sentence reading "Click #login > button" tells
 * nobody which button that is. So the token prefers the best candidate that
 * was recorded from something the page says out loud, and falls back to the
 * selector — marked as the machine string it is, which is what puts it in
 * monospace.
 */
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

/** "a list of " before the output name, or nothing at all for one value. */
function listed(mode: "scalar" | "list"): string {
  return mode === "list" ? "a list of " : "";
}

/**
 * A value split into the words and the Variables it mixes.
 *
 * Only a navigate URL and a type value are interpolated, so nothing else
 * comes through here: a `{{` in a select value is two characters the page
 * will receive.
 */
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

/**
 * The sentence with its empty parts dropped and its neighbouring words run
 * together, so that a card never draws two text nodes where one reads.
 */
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
