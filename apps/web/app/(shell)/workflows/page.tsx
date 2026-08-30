"use client";

import {
  createWorkflow,
  deleteWorkflow,
  duplicateWorkflow,
  renameWorkflow,
  type WorkflowSort,
  type WorkflowSummary,
} from "@step-by-step/api-client";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import type { WorkflowAction } from "./actions";
import { DeleteDialog } from "./delete-dialog";
import { FirstRunPanel } from "./first-run-panel";
import { SORT_OPTIONS, offersSearchAndSort } from "./list";
import { refusalMessage } from "./messages";
import { NameDialog } from "./name-dialog";
import { rowsOf, workflowsKey, workflowsQuery } from "./queries";
import { StartRunDialog } from "./start-run-dialog";
import { useStartRun } from "./use-start-run";
import { WorkflowRow } from "./workflow-row";

import { EDITOR, newBatchPath, newSchedulePath, tabPath } from "./[id]/tabs";

import { useActiveOrganization } from "../use-active-organization";

import { Callout } from "@/components/primitives/callout";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function WorkflowsPage() {
  const { active } = useActiveOrganization();

  if (active === null) {
    return null;
  }

  return <Workflows orgId={active.id} />;
}

type OpenDialog =
  | { kind: "none" }
  | { kind: "new" }
  | { kind: "rename"; workflow: WorkflowSummary }
  | { kind: "delete"; workflow: WorkflowSummary };

function Workflows({ orgId }: { orgId: string }) {
  const router = useRouter();
  const cache = useQueryClient();
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<WorkflowSort>("activity");
  const [dialog, setDialog] = useState<OpenDialog>({ kind: "none" });
  const startRun = useStartRun();

  const list = useInfiniteQuery(workflowsQuery(orgId, { q, sort }));
  const rows = rowsOf(list.data?.pages);

  const refresh = async () => {
    await cache.invalidateQueries({ queryKey: workflowsKey(orgId) });
  };

  const create = useMutation({
    mutationFn: async (name: string) => {
      const { data, error } = await createWorkflow({ body: { name } });
      if (error) throw error;
      return data;
    },
    onSuccess: async (made) => {
      setDialog({ kind: "none" });
      await refresh();
      router.push(tabPath(made.id, EDITOR));
    },
  });

  const rename = useMutation({
    mutationFn: async ({ id, name }: { id: string; name: string }) => {
      const { error } = await renameWorkflow({ path: { workflow_id: id }, body: { name } });
      if (error) throw error;
    },
    onSuccess: async () => {
      setDialog({ kind: "none" });
      await refresh();
    },
  });

  const duplicate = useMutation({
    mutationFn: async (id: string) => {
      const { error } = await duplicateWorkflow({ path: { workflow_id: id } });
      if (error) throw error;
    },
    onSuccess: refresh,
  });

  const remove = useMutation({
    mutationFn: async (id: string) => {
      const { error } = await deleteWorkflow({ path: { workflow_id: id } });
      if (error) throw error;
    },
    onSuccess: async () => {
      setDialog({ kind: "none" });
      await refresh();
    },
  });

  const act = (action: WorkflowAction, workflow: WorkflowSummary) => {
    if (action.key === "rename") {
      setDialog({ kind: "rename", workflow });
    } else if (action.key === "delete") {
      setDialog({ kind: "delete", workflow });
    } else if (action.key === "duplicate") {
      duplicate.mutate(workflow.id);
    } else if (action.key === "new-batch") {
      router.push(newBatchPath(workflow.id));
    } else if (action.key === "new-schedule") {
      router.push(newSchedulePath(workflow.id));
    } else if (action.key === "run") {
      startRun.begin(workflow);
    }
  };

  const searching = q !== "";
  const refused = list.error ?? duplicate.error ?? startRun.refusal;

  return (
    <>
      <div className="flex items-center gap-3">
        <h1 className="text-page">Workflows</h1>
        <Button
          className="ml-auto"
          onClick={() => {
            setDialog({ kind: "new" });
          }}
        >
          New workflow
        </Button>
      </div>

      {offersSearchAndSort(rows.length, searching) ? (
        <div className="flex items-center gap-2">
          <Input
            aria-label="Search Workflows"
            placeholder="Search by name"
            value={q}
            className="max-w-xs"
            onChange={(typed) => {
              setQ(typed.target.value);
            }}
          />
          <select
            aria-label="Sort"
            className="h-9 rounded-md border border-line bg-panel px-2 text-half text-ink"
            value={sort}
            onChange={(chosen) => {
              setSort(chosen.target.value as WorkflowSort);
            }}
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      ) : null}

      {refused ? <Callout tone="bad">{refusalMessage(refused)}</Callout> : null}

      {rows.length === 0 ? (
        searching ? (
          <Card className="px-3 py-4">
            <p className="text-half text-mut">No Workflow matches “{q}”.</p>
          </Card>
        ) : list.isPending ? null : (
          <FirstRunPanel
            onCreate={() => {
              setDialog({ kind: "new" });
            }}
          />
        )
      ) : (
        <Card className="p-0">
          <ul className="flex flex-col">
            {rows.map((workflow) => (
              <WorkflowRow key={workflow.id} workflow={workflow} onAction={act} />
            ))}
          </ul>
        </Card>
      )}

      {list.hasNextPage ? (
        <Button
          variant="ghost"
          className="self-center text-small"
          disabled={list.isFetchingNextPage}
          onClick={() => {
            void list.fetchNextPage();
          }}
        >
          Load more
        </Button>
      ) : null}

      <NameDialog
        open={dialog.kind === "new"}
        title="New workflow"
        description="Name it now; you record its steps next."
        submitLabel="Create"
        pending={create.isPending}
        refusal={create.error ? refusalMessage(create.error) : null}
        onSubmit={(name) => {
          create.mutate(name);
        }}
        onOpenChange={(open) => {
          if (!open) {
            setDialog({ kind: "none" });
          }
        }}
      />

      <NameDialog
        open={dialog.kind === "rename"}
        title="Rename workflow"
        description="What this Workflow is called, wherever it appears."
        submitLabel="Save"
        initialName={dialog.kind === "rename" ? dialog.workflow.name : ""}
        pending={rename.isPending}
        refusal={rename.error ? refusalMessage(rename.error) : null}
        onSubmit={(name) => {
          if (dialog.kind === "rename") {
            rename.mutate({ id: dialog.workflow.id, name });
          }
        }}
        onOpenChange={(open) => {
          if (!open) {
            setDialog({ kind: "none" });
          }
        }}
      />

      <DeleteDialog
        workflow={dialog.kind === "delete" ? dialog.workflow : null}
        pending={remove.isPending}
        refusal={remove.error ? refusalMessage(remove.error) : null}
        onConfirm={() => {
          if (dialog.kind === "delete") {
            remove.mutate(dialog.workflow.id);
          }
        }}
        onOpenChange={(open) => {
          if (!open) {
            setDialog({ kind: "none" });
          }
        }}
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
