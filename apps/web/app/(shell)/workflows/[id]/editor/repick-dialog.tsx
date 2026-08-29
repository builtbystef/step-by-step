"use client";

import type { SelectorCandidate } from "@step-by-step/api-client";

import { candidateKindTone, candidateUniqueness } from "./selectors";

import { Callout } from "@/components/primitives/callout";
import { AttributeBadge } from "@/components/primitives/attribute-badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

/**
 * Old versus new, after the extension has computed a fresh candidate list
 * and before anyone writes the Draft. Confirm is the existing Re-pick
 * finalize; cancel never calls it.
 */
export function RepickDialog({
  open,
  oldCandidates,
  newCandidates,
  pending,
  refusal,
  onConfirm,
  onOpenChange,
}: {
  open: boolean;
  oldCandidates: SelectorCandidate[];
  newCandidates: SelectorCandidate[];
  pending: boolean;
  refusal: string | null;
  onConfirm: () => void;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Replace how this step finds its element?</DialogTitle>
          <DialogDescription>
            Confirming patches this Step's candidate list and nothing else. Cancelling leaves the
            Draft untouched.
          </DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-4">
          <CandidateColumn heading="Current" candidates={oldCandidates} />
          <CandidateColumn heading="New" candidates={newCandidates} />
        </div>
        {refusal === null ? null : <Callout tone="bad">{refusal}</Callout>}
        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => {
              onOpenChange(false);
            }}
          >
            Cancel
          </Button>
          <Button disabled={pending} onClick={onConfirm}>
            Use the new selectors
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function CandidateColumn({
  heading,
  candidates,
}: {
  heading: string;
  candidates: SelectorCandidate[];
}) {
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-small font-semibold text-ink">{heading}</h3>
      {candidates.length === 0 ? (
        <p className="text-small text-mut">No selectors.</p>
      ) : (
        candidates.map((candidate, index) => {
          const uniqueness = candidateUniqueness(candidate);
          return (
            <div
              key={`${heading}:${candidate.kind}:${candidate.value}:${String(index)}`}
              className="flex items-center gap-2"
            >
              <span className="w-4 shrink-0 text-right text-micro text-mut">{index + 1}</span>
              <AttributeBadge tone={candidateKindTone(candidate.kind)}>
                {candidate.kind}
              </AttributeBadge>
              <span className="min-w-0 flex-1 truncate font-mono text-small text-ink">
                {candidate.value}
              </span>
              <span className="shrink-0 text-small text-ok" title={uniqueness.title}>
                ✓ {uniqueness.label}
              </span>
            </div>
          );
        })
      )}
    </div>
  );
}
