"use client";

import { Camera, ChevronDown, ChevronUp, Eye, EyeOff, Trash2 } from "lucide-react";

import { stepBadges } from "./badges";
import { Sentence } from "./sentence";
import { StepForm } from "./step-form";
import type { Step } from "./steps";
import { summarize } from "./summary";

import { AttributeBadge } from "@/components/primitives/attribute-badge";
import { cn } from "@/lib/utils";

/**
 * One Step, as a card that reads as a sentence.
 *
 * The label is bold and editable where it is; under it the Step in words;
 * down the right the badges; and the tools that reorder, switch off, and
 * delete appear on hover, so that a list of forty cards is a list rather than
 * a wall of buttons. Clicking the sentence expands the full form in place —
 * the card never becomes a second screen.
 *
 * A Step that is off stays exactly where it is, dimmed: it is part of the
 * Workflow, and hiding it would make a person wonder where it went.
 *
 * One thing in the badge column is a control rather than a statement: the
 * screenshot toggle, which the spec puts here beside optional and off. It is
 * lit when it is on and appears with the hover tools when it is not, because
 * a column of eight dormant cameras states nothing.
 */
export function StepCard({
  step,
  position,
  count,
  workflowDefaultMs,
  expanded,
  onExpand,
  onChange,
  onMove,
  onDelete,
}: {
  step: Step;
  position: number;
  count: number;
  workflowDefaultMs: number;
  expanded: boolean;
  onExpand: (expanded: boolean) => void;
  onChange: (step: Step) => void;
  onMove: (direction: "up" | "down") => void;
  onDelete: () => void;
}) {
  const badges = stepBadges(step, workflowDefaultMs);
  const off = step.disabled === true;

  return (
    <li className="group flex gap-3 border-b border-line px-3 py-3 last:border-b-0">
      <span className="mt-2 w-5 shrink-0 text-right text-micro text-mut">{position + 1}</span>

      <div className={cn("flex min-w-0 flex-1 flex-col gap-1", off && "opacity-60")}>
        <input
          aria-label={`Label of step ${String(position + 1)}`}
          className="w-full rounded-sm bg-transparent text-half font-semibold text-ink outline-hidden hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
          value={step.label}
          onChange={(typed) => {
            onChange({ ...step, label: typed.target.value });
          }}
        />
        <button
          type="button"
          aria-expanded={expanded}
          className="w-full cursor-pointer text-left"
          onClick={() => {
            onExpand(!expanded);
          }}
        >
          <Sentence segments={summarize(step)} />
        </button>
        {expanded ? (
          <StepForm step={step} workflowDefaultMs={workflowDefaultMs} onChange={onChange} />
        ) : null}
      </div>

      <div className="flex shrink-0 items-start gap-1 opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100">
        <Tool
          label={`Move step ${String(position + 1)} up`}
          disabled={position === 0}
          onClick={() => {
            onMove("up");
          }}
        >
          <ChevronUp className="size-4" />
        </Tool>
        <Tool
          label={`Move step ${String(position + 1)} down`}
          disabled={position === count - 1}
          onClick={() => {
            onMove("down");
          }}
        >
          <ChevronDown className="size-4" />
        </Tool>
        <Tool
          label={
            off
              ? `Switch step ${String(position + 1)} on`
              : `Switch step ${String(position + 1)} off`
          }
          onClick={() => {
            onChange({ ...step, disabled: !off });
          }}
        >
          {off ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </Tool>
        <Tool label={`Delete step ${String(position + 1)}`} destructive onClick={onDelete}>
          <Trash2 className="size-4" />
        </Tool>
      </div>

      <div className="flex w-36 shrink-0 flex-wrap items-start justify-end gap-1">
        {badges.map((badge) => (
          <AttributeBadge key={badge.key} tone={badge.tone}>
            <span title={badge.title}>{badge.label}</span>
          </AttributeBadge>
        ))}
        <button
          type="button"
          aria-label={`Screenshot after step ${String(position + 1)}`}
          aria-pressed={step.screenshot === true}
          title={
            step.screenshot === true
              ? "A screenshot is kept after this Step. A failing Step is captured either way."
              : "Keep a screenshot after this Step. A failing Step is captured either way."
          }
          className={cn(
            "flex size-5 items-center justify-center rounded-md outline-hidden focus-visible:ring-2 focus-visible:ring-ring",
            step.screenshot === true
              ? "bg-accent-bg text-accent"
              : "text-mut opacity-0 group-focus-within:opacity-100 group-hover:opacity-100 hover:text-accent",
          )}
          onClick={() => {
            onChange({ ...step, screenshot: step.screenshot !== true });
          }}
        >
          <Camera className="size-3.5" />
        </button>
      </div>
    </li>
  );
}

function Tool({
  label,
  disabled,
  destructive,
  onClick,
  children,
}: {
  label: string;
  disabled?: boolean;
  destructive?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      className={cn(
        "flex size-7 items-center justify-center rounded-md text-mut outline-hidden hover:bg-accent-bg hover:text-accent focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-30",
        destructive === true && "hover:bg-bad-bg hover:text-bad",
      )}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
