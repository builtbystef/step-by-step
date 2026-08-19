"use client";

import type { WorkflowSummary } from "@step-by-step/api-client";
import { MoreHorizontal, Play } from "lucide-react";
import Link from "next/link";

import { OVERFLOW_ACTIONS, RUN, disabledReason, type WorkflowAction } from "./actions";
import { draftStateBadge } from "./draft-state";

import { EDITOR, tabPath } from "./[id]/tabs";

import { AttributeBadge } from "@/components/primitives/attribute-badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { relativeTime } from "@/lib/relative-time";
import { cn } from "@/lib/utils";

/**
 * One Workflow in the list.
 *
 * The name is the row and the row is a link: clicking anywhere that is not an
 * action opens the editor. Everything else is secondary — the meta line
 * underneath, and the draft-state badge on the right, which is an
 * `AttributeBadge` because a draft state is a property and not a lifecycle
 * state.
 *
 * The last Run and the schedule indicator the meta line will also carry arrive
 * with the slice that gives a Workflow either; until then every Workflow has
 * never run, which is what it says.
 */
export function WorkflowRow({
  workflow,
  onAction,
}: {
  workflow: WorkflowSummary;
  onAction: (action: WorkflowAction, workflow: WorkflowSummary) => void;
}) {
  const badge = draftStateBadge(workflow.draft_state, workflow.published_version);
  const runRefusal = disabledReason(RUN, workflow.draft_state);

  return (
    <li className="group relative flex items-center gap-3 border-b border-line px-3 py-3 last:border-b-0 hover:bg-accent-bg/40">
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <Link
          href={tabPath(workflow.id, EDITOR)}
          className="text-half font-semibold text-ink after:absolute after:inset-0 after:content-['']"
        >
          {workflow.name}
        </Link>
        <p className="text-small text-mut">
          never run · edited {relativeTime(workflow.last_activity_at)}
        </p>
      </div>

      <div className="relative z-10 flex items-center gap-1 opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100">
        <Button
          size="sm"
          variant="ghost"
          className="text-small"
          disabled={runRefusal !== null}
          title={runRefusal ?? undefined}
          onClick={() => {
            onAction(RUN, workflow);
          }}
        >
          <Play className="size-3.5" />
          Run
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger
            aria-label={`More for ${workflow.name}`}
            className="flex size-8 items-center justify-center rounded-md text-mut outline-hidden hover:bg-accent-bg hover:text-accent focus-visible:ring-2 focus-visible:ring-ring"
          >
            <MoreHorizontal className="size-4" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {OVERFLOW_ACTIONS.map((action) => {
              const refusal = disabledReason(action, workflow.draft_state);
              return (
                <DropdownMenuItem
                  key={action.key}
                  disabled={refusal !== null}
                  title={refusal ?? undefined}
                  className={cn(action.destructive === true && "text-bad")}
                  onClick={() => {
                    onAction(action, workflow);
                  }}
                >
                  {action.label}
                </DropdownMenuItem>
              );
            })}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <AttributeBadge tone={badge.tone} className="relative z-10 shrink-0">
        {badge.label}
      </AttributeBadge>
    </li>
  );
}
