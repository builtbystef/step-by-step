"use client";

import { saveWorkflowDraft, type WorkflowDocument } from "@step-by-step/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";

import { withStepAdded, withStepDeleted, withStepMoved, withStepReplaced } from "./edits";
import { saveRefusal } from "./messages";
import { draftKey, draftQuery } from "./queries";
import { StepCard } from "./step-card";
import { ADDABLE_STEP_TYPES, STEP_TYPE_LABELS, blankStep, type Step } from "./steps";

import { workflowKey, workflowQuery } from "../queries";

import { workflowsKey } from "../../queries";

import { useActiveOrganization } from "../../../use-active-organization";

import { Callout } from "@/components/primitives/callout";
import { EmptyState } from "@/components/primitives/empty-state";
import { StickyActionFooter } from "@/components/primitives/sticky-action-footer";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

/**
 * Workflow ▸ Editor — the Draft as a vertical card list that reads as
 * sentences, and everything a person does to it short of publishing.
 *
 * The document is edited whole and saved whole, because that is what the
 * Draft API is: a save replaces the document, and validation reads it as one
 * thing. So the screen holds one edited copy, every tool hands back the next
 * one, and the footer sends it. Nothing is saved as you type — a Draft that
 * saved on every keystroke would be a hundred rejected documents on the way
 * to one good one.
 *
 * Three things on this tab belong to later slices and are deliberately not
 * here: the selector panel behind a target's badge (`m6s5me`), the Variables
 * drawer and pill insertion (`z8p5dp`), and recording, test runs, and
 * publishing (`7vuup5`, `2ggmhx`, `fq0wr7`).
 */
export default function EditorTab() {
  const { active } = useActiveOrganization();
  const params = useParams<{ id: string }>();

  if (active === null) {
    return null;
  }

  return <DraftEditor orgId={active.id} workflowId={params.id} />;
}

function DraftEditor({ orgId, workflowId }: { orgId: string; workflowId: string }) {
  const cache = useQueryClient();
  const draft = useQuery(draftQuery(orgId, workflowId));
  const workflow = useQuery(workflowQuery(orgId, workflowId));
  const [edited, setEdited] = useState<WorkflowDocument | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: async (document: WorkflowDocument) => {
      const { data, error } = await saveWorkflowDraft({
        path: { workflow_id: workflowId },
        body: document,
      });
      if (error) throw error;
      return data;
    },
    onSuccess: async () => {
      setEdited(null);
      await Promise.all([
        cache.invalidateQueries({ queryKey: draftKey(orgId, workflowId) }),
        // The Draft chip in the header and the row in the list both read where
        // the Draft stands against the published Version, and a save is what
        // moves it.
        cache.invalidateQueries({ queryKey: workflowKey(orgId, workflowId) }),
        cache.invalidateQueries({ queryKey: workflowsKey(orgId) }),
      ]);
    },
  });

  // The edited copy wins while there is one, so a background refetch cannot
  // take somebody's unsaved work away from under them.
  const document = edited ?? draft.data ?? null;
  const steps = document?.steps ?? [];
  const unsaved = edited !== null;
  const workflowDefaultMs = workflow.data?.default_step_timeout_ms ?? 30_000;

  if (document === null) {
    return draft.error ? <Callout tone="bad">{saveRefusal(draft.error)}</Callout> : null;
  }

  const add = (type: (typeof ADDABLE_STEP_TYPES)[number]) => {
    const step = blankStep(type);
    setEdited(withStepAdded(document, step));
    setExpanded(step.id);
  };

  const addMenu = (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button variant="secondary">
            <Plus className="size-3.5" />
            Add step
          </Button>
        }
      />
      <DropdownMenuContent align="end">
        {ADDABLE_STEP_TYPES.map((type) => (
          <DropdownMenuItem
            key={type}
            onClick={() => {
              add(type);
            }}
          >
            {STEP_TYPE_LABELS[type]}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );

  return (
    <>
      {save.error ? <Callout tone="bad">{saveRefusal(save.error)}</Callout> : null}

      {steps.length === 0 ? (
        <EmptyState
          absence="This Workflow has no steps yet"
          whatFillsIt="Record what you do in your own browser, or add a step here by hand."
          action={addMenu}
        />
      ) : (
        <>
          <Card className="p-0">
            <ul className="flex flex-col">
              {steps.map((step, position) => (
                <StepCard
                  key={step.id}
                  step={step}
                  position={position}
                  count={steps.length}
                  workflowDefaultMs={workflowDefaultMs}
                  expanded={expanded === step.id}
                  onExpand={(open) => {
                    setExpanded(open ? step.id : null);
                  }}
                  onChange={(next: Step) => {
                    setEdited(withStepReplaced(document, next));
                  }}
                  onMove={(direction) => {
                    setEdited(withStepMoved(document, step.id, direction));
                  }}
                  onDelete={() => {
                    setEdited(withStepDeleted(document, step.id));
                  }}
                />
              ))}
            </ul>
          </Card>
          <div className="flex justify-end">{addMenu}</div>
        </>
      )}

      {unsaved ? (
        <StickyActionFooter>
          <p className="mr-auto text-small text-mut">
            Unsaved changes — nothing runs from this Draft until you save it.
          </p>
          <Button
            variant="ghost"
            disabled={save.isPending}
            onClick={() => {
              setEdited(null);
            }}
          >
            Discard
          </Button>
          <Button
            disabled={save.isPending}
            onClick={() => {
              save.mutate(document);
            }}
          >
            Save
          </Button>
        </StickyActionFooter>
      ) : null}
    </>
  );
}
