"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MoreHorizontal, Play } from "lucide-react";
import Link from "next/link";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

import { workflowKey, workflowQuery } from "./queries";
import { EDITOR, WORKFLOW_TABS, tabAt, tabPath } from "./tabs";

import { OVERFLOW_ACTIONS, RUN, disabledReason, type WorkflowAction } from "../actions";
import { DeleteDialog } from "../delete-dialog";
import { draftStateBadge } from "../draft-state";
import { refusalMessage } from "../messages";
import { NameDialog } from "../name-dialog";
import { workflowsKey } from "../queries";

import { useActiveOrganization } from "../../use-active-organization";

import { deleteWorkflow, duplicateWorkflow, renameWorkflow } from "@step-by-step/api-client";
import { AttributeBadge } from "@/components/primitives/attribute-badge";
import { Callout } from "@/components/primitives/callout";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

/**
 * The Workflow page: one header over four tabs.
 *
 * The header is the layout's rather than each tab's, so that the name, the
 * draft-state chip, and the Run action are there from every tab — switching
 * tab is a navigation inside a Workflow, not a different screen about it.
 *
 * The overflow repeats the list row's actions, from the one list of them, so
 * that where you are never changes what you can do.
 */
export default function WorkflowLayout({ children }: { children: ReactNode }) {
  const { active } = useActiveOrganization();
  const params = useParams<{ id: string }>();

  if (active === null) {
    return null;
  }

  return (
    <WorkflowFrame orgId={active.id} workflowId={params.id}>
      {children}
    </WorkflowFrame>
  );
}

function WorkflowFrame({
  orgId,
  workflowId,
  children,
}: {
  orgId: string;
  workflowId: string;
  children: ReactNode;
}) {
  const router = useRouter();
  const cache = useQueryClient();
  const pathname = usePathname();
  const [renaming, setRenaming] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const workflow = useQuery(workflowQuery(orgId, workflowId));
  const here = tabAt(pathname) ?? EDITOR;

  const refresh = async () => {
    await Promise.all([
      cache.invalidateQueries({ queryKey: workflowKey(orgId, workflowId) }),
      cache.invalidateQueries({ queryKey: workflowsKey(orgId) }),
    ]);
  };

  const rename = useMutation({
    mutationFn: async (name: string) => {
      const { error } = await renameWorkflow({
        path: { workflow_id: workflowId },
        body: { name },
      });
      if (error) throw error;
    },
    onSuccess: async () => {
      setRenaming(false);
      await refresh();
    },
  });

  const duplicate = useMutation({
    mutationFn: async () => {
      const { data, error } = await duplicateWorkflow({ path: { workflow_id: workflowId } });
      if (error) throw error;
      return data;
    },
    onSuccess: async (copy) => {
      await refresh();
      router.push(tabPath(copy.id, EDITOR));
    },
  });

  const remove = useMutation({
    mutationFn: async () => {
      const { error } = await deleteWorkflow({ path: { workflow_id: workflowId } });
      if (error) throw error;
    },
    onSuccess: async () => {
      setDeleting(false);
      await refresh();
      router.push("/workflows");
    },
  });

  const act = (action: WorkflowAction) => {
    if (action.key === "rename") {
      setRenaming(true);
    } else if (action.key === "delete") {
      setDeleting(true);
    } else if (action.key === "duplicate") {
      duplicate.mutate();
    }
    // Run, New batch, and New schedule act on a Version; the slices that build
    // their forms hang them off this same header.
  };

  const state = workflow.data?.draft_state ?? "never-published";
  const badge = draftStateBadge(state, workflow.data?.published_version);
  const runRefusal = disabledReason(RUN, state);
  const refused = workflow.error ?? duplicate.error ?? remove.error;

  return (
    <>
      <div className="flex items-center gap-3">
        <h1 className="text-page">{workflow.data?.name ?? " "}</h1>
        {workflow.data ? <AttributeBadge tone={badge.tone}>{badge.label}</AttributeBadge> : null}
        <div className="ml-auto flex items-center gap-1">
          <Button
            variant="secondary"
            disabled={runRefusal !== null}
            title={runRefusal ?? undefined}
            onClick={() => {
              act(RUN);
            }}
          >
            <Play className="size-3.5" />
            Run
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger
              aria-label="More"
              className="flex size-9 items-center justify-center rounded-md text-mut outline-hidden hover:bg-accent-bg hover:text-accent focus-visible:ring-2 focus-visible:ring-ring"
            >
              <MoreHorizontal className="size-4" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {OVERFLOW_ACTIONS.map((action) => {
                const refusal = disabledReason(action, state);
                return (
                  <DropdownMenuItem
                    key={action.key}
                    disabled={refusal !== null}
                    title={refusal ?? undefined}
                    className={cn(action.destructive === true && "text-bad")}
                    onClick={() => {
                      act(action);
                    }}
                  >
                    {action.label}
                  </DropdownMenuItem>
                );
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <nav aria-label="Workflow" className="flex gap-1 border-b border-line">
        {WORKFLOW_TABS.map((tab) => (
          <Link
            key={tab.segment}
            href={tabPath(workflowId, tab)}
            aria-current={tab.segment === here.segment ? "page" : undefined}
            className={cn(
              "-mb-px border-b-2 border-transparent px-3 py-2 text-half text-mut hover:text-ink",
              tab.segment === here.segment && "border-accent font-semibold text-accent",
            )}
          >
            {tab.label}
          </Link>
        ))}
      </nav>

      {refused ? <Callout tone="bad">{refusalMessage(refused)}</Callout> : null}

      {children}

      <NameDialog
        open={renaming}
        title="Rename workflow"
        description="What this Workflow is called, wherever it appears."
        submitLabel="Save"
        initialName={workflow.data?.name ?? ""}
        pending={rename.isPending}
        refusal={rename.error ? refusalMessage(rename.error) : null}
        onSubmit={(name) => {
          rename.mutate(name);
        }}
        onOpenChange={setRenaming}
      />

      <DeleteDialog
        workflow={deleting ? (workflow.data ?? null) : null}
        pending={remove.isPending}
        refusal={remove.error ? refusalMessage(remove.error) : null}
        onConfirm={() => {
          remove.mutate();
        }}
        onOpenChange={setDeleting}
      />
    </>
  );
}
