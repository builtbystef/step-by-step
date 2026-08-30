"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, History, MoreHorizontal, Play, Upload } from "lucide-react";
import Link from "next/link";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState, type ReactNode } from "react";

import { PublishDialog } from "./publish-dialog";
import {
  draftDiffKey,
  draftDiffQuery,
  versionsKey,
  versionsQuery,
  workflowKey,
  workflowQuery,
} from "./queries";
import { EDITOR, WORKFLOW_TABS, newBatchPath, newSchedulePath, tabAt, tabPath } from "./tabs";
import { versionChoices, versionPath, viewedVersion } from "./versions";

import { OVERFLOW_ACTIONS, RUN, disabledReason, type WorkflowAction } from "../actions";
import { DeleteDialog } from "../delete-dialog";
import { draftStateBadge } from "../draft-state";
import { refusalMessage } from "../messages";
import { NameDialog } from "../name-dialog";
import { workflowsKey } from "../queries";
import { StartRunDialog } from "../start-run-dialog";
import { useStartRun } from "../use-start-run";

import { useActiveOrganization } from "../../use-active-organization";

import {
  deleteWorkflow,
  duplicateWorkflow,
  publishWorkflowVersion,
  renameWorkflow,
  type VersionSummary,
} from "@step-by-step/api-client";
import { AttributeBadge } from "@/components/primitives/attribute-badge";
import { Callout } from "@/components/primitives/callout";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { relativeTime } from "@/lib/relative-time";
import { cn } from "@/lib/utils";

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
  const [publishing, setPublishing] = useState(false);
  const startRun = useStartRun();

  const workflow = useQuery(workflowQuery(orgId, workflowId));
  const versions = useQuery(versionsQuery(orgId, workflowId));
  const diff = useQuery(draftDiffQuery(orgId, workflowId, publishing));
  const here = tabAt(pathname) ?? EDITOR;
  const viewing = viewedVersion(useSearchParams().get("version"));

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

  const publish = useMutation({
    mutationFn: async () => {
      const { error } = await publishWorkflowVersion({ path: { workflow_id: workflowId } });
      if (error) throw error;
    },
    onSuccess: async () => {
      setPublishing(false);
      await Promise.all([
        refresh(),
        cache.invalidateQueries({ queryKey: versionsKey(orgId, workflowId) }),
        cache.invalidateQueries({ queryKey: draftDiffKey(orgId, workflowId) }),
      ]);
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
    } else if (action.key === "new-batch") {
      router.push(newBatchPath(workflowId));
    } else if (action.key === "new-schedule") {
      router.push(newSchedulePath(workflowId));
    } else if (action.key === "run" && workflow.data !== undefined) {
      startRun.begin(workflow.data);
    }
  };

  const state = workflow.data?.draft_state ?? "never-published";
  const badge = draftStateBadge(state, workflow.data?.published_version);
  const runRefusal = disabledReason(RUN, state);
  const publishRefusal =
    viewing === null ? null : "Publishing publishes the Draft. Open the Draft to publish it.";
  const refused = workflow.error ?? duplicate.error ?? remove.error ?? startRun.refusal;

  return (
    <>
      <div className="flex items-center gap-3">
        <h1 className="text-page">{workflow.data?.name ?? " "}</h1>
        {workflow.data ? <AttributeBadge tone={badge.tone}>{badge.label}</AttributeBadge> : null}
        <VersionMenu workflowId={workflowId} versions={versions.data ?? []} viewing={viewing} />
        <div className="ml-auto flex items-center gap-1">
          <Button
            disabled={publishRefusal !== null}
            title={publishRefusal ?? undefined}
            onClick={() => {
              setPublishing(true);
            }}
          >
            <Upload className="size-3.5" />
            Publish
          </Button>
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

      <PublishDialog
        open={publishing}
        comparison={publishing ? (diff.data ?? null) : null}
        pending={publish.isPending}
        refusal={(diff.error ?? publish.error) ? refusalMessage(diff.error ?? publish.error) : null}
        onConfirm={() => {
          publish.mutate();
        }}
        onOpenChange={setPublishing}
      />

      <StartRunDialog
        open={startRun.dialog !== null}
        variables={startRun.dialog?.variables ?? []}
        pending={startRun.pending}
        refusal={startRun.refusal ? refusalMessage(startRun.refusal) : null}
        onSubmit={(row) => {
          if (startRun.dialog !== null) {
            startRun.startFromGrid(startRun.dialog.workflowId, startRun.dialog.variables, row);
          }
        }}
        onOpenChange={(open) => {
          if (!open) {
            startRun.close();
          }
        }}
      />
    </>
  );
}

function VersionMenu({
  workflowId,
  versions,
  viewing,
}: {
  workflowId: string;
  versions: VersionSummary[];
  viewing: number | null;
}) {
  const choices = versionChoices(versions, viewing);
  const open = choices.find((choice) => choice.open) ?? choices[0];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button variant="secondary" size="sm">
            <History className="size-3.5" />
            {open?.label ?? "Draft"}
            <ChevronDown className="size-3.5 text-mut" />
          </Button>
        }
      />
      <DropdownMenuContent align="start">
        {choices.map((choice) => (
          <DropdownMenuItem
            key={choice.label}
            render={<Link href={versionPath(workflowId, choice.version)} />}
            className={cn(choice.open && "font-semibold text-accent")}
          >
            {choice.label}
            {choice.publishedAt === null ? null : (
              <span className="ml-2 text-micro text-mut">
                published {relativeTime(choice.publishedAt)}
              </span>
            )}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
