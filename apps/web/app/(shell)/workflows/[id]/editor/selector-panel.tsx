"use client";

import type { CandidateKind, SelectorCandidate, Target } from "@step-by-step/api-client";
import { useState } from "react";

import { healthOf } from "./badges";
import {
  CANDIDATE_KINDS,
  candidateKindTone,
  candidateUniqueness,
  selectorHealthCopy,
  selectorHealthTone,
  withCandidateAdded,
  withCandidateMovedToTop,
  withCandidateRemoved,
  withCandidates,
} from "./selectors";
import { targetToken } from "./summary";

import { AttributeBadge } from "@/components/primitives/attribute-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export function SelectorPanel({
  target,
  label = "Element",
  open = false,
  onChange,
  onRepick,
}: {
  target: Target;
  label?: string;
  open?: boolean;
  onChange: (target: Target) => void;
  onRepick?: () => void;
}) {
  const token = targetToken(target);
  const health = healthOf(target);
  const count = target.candidates.length;
  const [adding, setAdding] = useState({ kind: "css" as CandidateKind, value: "" });

  const edit = (candidates: SelectorCandidate[]) => {
    onChange(withCandidates(target, candidates));
  };

  return (
    <div className="flex flex-col gap-1">
      <span className="text-small font-semibold text-ink">{label}</span>
      <details className="group rounded-lg border border-line bg-panel" open={open || undefined}>
        <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2 [&::-webkit-details-marker]:hidden">
          <span className="text-small text-mut transition-transform group-open:rotate-90">▸</span>
          <span className="min-w-0 flex-1 text-half font-semibold text-ink">
            How this step finds{" "}
            <span className={cn(token.machine && "font-mono text-small")}>'{token.text}'</span>
          </span>
          <AttributeBadge tone={selectorHealthTone(health, count)}>
            {selectorHealthCopy(health, count)}
          </AttributeBadge>
        </summary>
        <div className="flex flex-col gap-2 border-t border-line px-3 py-2">
          <p className="text-small text-mut">
            Tried top-to-bottom at replay; the first that matches exactly one element wins.
          </p>
          {target.candidates.map((candidate, index) => {
            const uniqueness = candidateUniqueness(candidate);
            return (
              <div
                key={`${candidate.kind}:${candidate.value}:${String(index)}`}
                className="flex items-center gap-2"
              >
                <span className="w-4 shrink-0 text-right text-micro text-mut">{index + 1}</span>
                <AttributeBadge tone={candidateKindTone(candidate.kind)}>
                  {candidate.kind}
                </AttributeBadge>
                <span className="min-w-0 flex-1 truncate rounded-md bg-muted px-1.5 py-0.5 font-mono text-small text-ink">
                  {candidate.value}
                </span>
                <span className="shrink-0 text-small text-ok" title={uniqueness.title}>
                  ✓ {uniqueness.label}
                </span>
                <span className="flex shrink-0 gap-1">
                  {index === 0 ? null : (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-small"
                      onClick={() => {
                        edit(withCandidateMovedToTop(target.candidates, index));
                      }}
                    >
                      top
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-small"
                    onClick={() => {
                      edit(withCandidateRemoved(target.candidates, index));
                    }}
                  >
                    remove
                  </Button>
                </span>
              </div>
            );
          })}
          <div className="flex flex-wrap items-end gap-2 pt-1">
            {onRepick === undefined ? null : (
              <Button variant="secondary" size="sm" className="text-small" onClick={onRepick}>
                Pick element again…
              </Button>
            )}
            <select
              aria-label="Selector kind"
              className="h-8 rounded-md border border-line bg-panel px-2 text-small text-ink"
              value={adding.kind}
              onChange={(chosen) => {
                setAdding({ ...adding, kind: chosen.target.value as CandidateKind });
              }}
            >
              {CANDIDATE_KINDS.map((kind) => (
                <option key={kind} value={kind}>
                  {kind}
                </option>
              ))}
            </select>
            <Input
              aria-label="Selector value"
              placeholder="Add selector by hand"
              className="h-8 w-48 font-mono text-small"
              value={adding.value}
              onChange={(typed) => {
                setAdding({ ...adding, value: typed.target.value });
              }}
            />
            <Button
              variant="secondary"
              size="sm"
              className="text-small"
              disabled={adding.value.trim() === ""}
              onClick={() => {
                const value = adding.value.trim();
                if (value === "") return;
                edit(withCandidateAdded(target.candidates, { kind: adding.kind, value }));
                setAdding({ kind: adding.kind, value: "" });
              }}
            >
              Add selector by hand
            </Button>
          </div>
        </div>
      </details>
    </div>
  );
}
