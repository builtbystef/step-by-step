"use client";

import { createBatch, type CreateBatch, type Variable } from "@step-by-step/api-client";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import {
  addedVariables,
  createBody,
  creationDriftBanner,
  defaultBatchName,
  mergeVariables,
  progressHref,
  rerunBatchName,
  sequentialEta,
  submitBlockedByDrift,
} from "./creation";
import { refusalMessage } from "./messages";
import { loadBatch, loadPublishedVariables, workflowBatchesQuery } from "./queries";

import { versionDocumentQuery } from "../../editor/queries";
import { workflowQuery } from "../../queries";

import { useActiveOrganization } from "../../../../use-active-organization";

import {
  CsvImportPanel,
  ValueGrid,
  applyCopiedBatch,
  assignHeader,
  beginImport,
  columnsOf,
  confirmImport,
  dismissSummary,
  fillEveryRow,
  initialRows,
  reopenSummary,
  rowCounts,
  stripFromSummary,
  type GridRow,
  type ImportPanel,
} from "@/components/value-grid";
import { Callout } from "@/components/primitives/callout";
import { StickyActionFooter } from "@/components/primitives/sticky-action-footer";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { COPY } from "@/lib/copy";

export default function NewBatchPage() {
  const { active } = useActiveOrganization();
  const params = useParams<{ id: string }>();

  if (active === null) {
    return null;
  }

  return <NewBatch orgId={active.id} workflowId={params.id} />;
}

function NewBatch({ orgId, workflowId }: { orgId: string; workflowId: string }) {
  const router = useRouter();
  const workflow = useQuery(workflowQuery(orgId, workflowId));
  const published = workflow.data?.published_version ?? null;
  const document = useQuery(versionDocumentQuery(orgId, workflowId, published));
  const past = useQuery(workflowBatchesQuery(orgId, workflowId));

  const [declared, setDeclared] = useState<Variable[] | null>(null);
  const [rows, setRows] = useState<GridRow[] | null>(null);
  const [name, setName] = useState<string | null>(null);
  const [runIncomplete, setRunIncomplete] = useState(false);
  const [added, setAdded] = useState<Variable[]>([]);
  const [fillValue, setFillValue] = useState("");
  const [checkError, setCheckError] = useState<unknown>(null);
  const [importPanel, setImportPanel] = useState<ImportPanel>({ kind: "idle" });
  const baselineNames = useRef<string[]>([]);
  const csvFile = useRef<HTMLInputElement>(null);

  const variables: Variable[] = declared ?? [];
  const columns = columnsOf(variables);

  useEffect(() => {
    if (document.data === undefined || rows !== null) {
      return;
    }
    const loaded = document.data.variables ?? [];
    setDeclared(loaded);
    baselineNames.current = loaded
      .filter((variable) => variable.secret !== true)
      .map((variable) => variable.name);
    setRows(initialRows(loaded, 1));
  }, [document.data, rows]);

  useEffect(() => {
    const onFocus = () => {
      void loadPublishedVariables(workflowId)
        .then((latest) => {
          const next = addedVariables(baselineNames.current, latest);
          if (next.length > 0) {
            setAdded(next);
            setDeclared((current) => mergeVariables(current ?? [], next));
          }
        })
        .catch(() => {});
    };
    window.addEventListener("focus", onFocus);
    return () => {
      window.removeEventListener("focus", onFocus);
    };
  }, [workflowId]);

  const copy = useMutation({
    mutationFn: async (batchId: string) => {
      const detail = await loadBatch(batchId);
      return detail;
    },
    onSuccess: (detail) => {
      setRows(applyCopiedBatch(columns, detail.rows));
      const workflowName = workflow.data?.name ?? "";
      setName(rerunBatchName(workflowName, detail.batch.name));
    },
  });

  const create = useMutation({
    mutationFn: async (body: CreateBatch) => {
      const { data, error } = await createBatch({
        path: { workflow_id: workflowId },
        body,
      });
      if (error) throw error;
      return data;
    },
    onSuccess: (created) => {
      router.push(progressHref(created.batch_id));
    },
  });

  if (workflow.error) {
    return <Callout tone="bad">{refusalMessage(workflow.error)}</Callout>;
  }
  if (document.error) {
    return <Callout tone="bad">{refusalMessage(document.error)}</Callout>;
  }
  if (published === null && workflow.data !== undefined) {
    return <Callout tone="bad">{COPY.noPublishedVersion}</Callout>;
  }
  if (
    workflow.data === undefined ||
    document.data === undefined ||
    rows === null ||
    declared === null
  ) {
    return null;
  }

  const shownName = name ?? defaultBatchName(workflow.data.name, new Date());
  const counts = rowCounts(rows, columns);
  const eta = sequentialEta(rows.length, workflow.data.recent_run_median_ms);
  const refused = copy.error ?? create.error ?? checkError;
  const banner = creationDriftBanner(added);

  const fillAdded = () => {
    if (banner === null) {
      return;
    }
    setRows(fillEveryRow(rows, columns, banner.name, fillValue));
    baselineNames.current = [...baselineNames.current, banner.name];
    setAdded((current) => current.filter((variable) => variable.name !== banner.name));
    setFillValue("");
  };

  const landCsv = (file: File) => {
    void file.text().then((text) => {
      const outcome = beginImport(text, variables, columns);
      if (outcome.kind === "landed") {
        setRows(outcome.rows);
      }
      setImportPanel(outcome.panel);
    });
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-title font-semibold">New batch</h2>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <input
            ref={csvFile}
            type="file"
            accept=".csv,text/csv,text/tab-separated-values,.tsv"
            className="hidden"
            onChange={(picked) => {
              const file = picked.target.files?.[0];
              picked.target.value = "";
              if (file !== undefined) {
                landCsv(file);
              }
            }}
          />
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              csvFile.current?.click();
            }}
          >
            Import CSV
          </Button>
          {importPanel.kind === "summary" && importPanel.dismissed ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setImportPanel(reopenSummary(importPanel));
              }}
            >
              Import summary
            </Button>
          ) : null}
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button variant="secondary" size="sm">
                  Copy from a past Batch
                </Button>
              }
            />
            <DropdownMenuContent align="end" className="min-w-56">
              {(past.data ?? []).length === 0 ? (
                <DropdownMenuItem disabled>No past Batches yet</DropdownMenuItem>
              ) : (
                (past.data ?? []).map((batch) => (
                  <DropdownMenuItem
                    key={batch.id}
                    onClick={() => {
                      copy.mutate(batch.id);
                    }}
                  >
                    {batch.name}
                  </DropdownMenuItem>
                ))
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {refused ? <Callout tone="bad">{refusalMessage(refused)}</Callout> : null}

      <CsvImportPanel
        panel={importPanel}
        onAssign={(variableName, header) => {
          if (importPanel.kind === "strip") {
            setImportPanel(assignHeader(importPanel, variableName, header));
          }
        }}
        onConfirm={() => {
          if (importPanel.kind !== "strip") {
            return;
          }
          const confirmed = confirmImport(importPanel, columns);
          setRows(confirmed.rows);
          setImportPanel(confirmed.panel);
        }}
        onDismiss={() => {
          if (importPanel.kind === "summary") {
            setImportPanel(dismissSummary(importPanel));
          }
        }}
        onChangeMapping={() => {
          if (importPanel.kind === "summary") {
            setImportPanel(stripFromSummary(importPanel));
          }
        }}
      />

      {banner === null ? null : (
        <Callout
          tone="warn"
          size="banner"
          title={banner.title}
          actions={
            <Button size="sm" disabled={fillValue.trim() === ""} onClick={fillAdded}>
              {banner.offer}
            </Button>
          }
        >
          <Input
            aria-label={banner.name}
            value={fillValue}
            className="h-7 max-w-xs font-mono text-half"
            onChange={(typed) => {
              setFillValue(typed.target.value);
            }}
          />
        </Callout>
      )}

      <ValueGrid variables={variables} rows={rows} onChange={setRows} />

      <StickyActionFooter className="flex-wrap justify-between gap-3">
        <div className="mr-auto flex min-w-0 flex-1 flex-col gap-2">
          <label className="flex min-w-0 items-center gap-2 text-small text-mut">
            Name
            <Input
              aria-label="Batch name"
              value={shownName}
              className="h-7 max-w-md text-half"
              onChange={(typed) => {
                setName(typed.target.value);
              }}
            />
          </label>
          <p className="text-small text-mut">
            {String(counts.total)} total · {String(counts.complete)} complete ·{" "}
            {String(counts.missing)} missing a value
          </p>
          <label className="flex items-center gap-2 text-half text-ink">
            <input
              type="checkbox"
              className="size-4 accent-accent"
              checked={runIncomplete}
              onChange={(ticked) => {
                setRunIncomplete(ticked.target.checked);
              }}
            />
            Run them anyway
          </label>
          <p className="text-small text-ink">{eta}</p>
        </div>
        <Button
          disabled={create.isPending || rows.length === 0}
          onClick={() => {
            void loadPublishedVariables(workflowId)
              .then((latest) => {
                const next = addedVariables(baselineNames.current, latest);
                if (next.length > 0) {
                  setAdded(next);
                  setDeclared((current) => mergeVariables(current ?? [], next));
                }
                if (submitBlockedByDrift(next)) {
                  return;
                }
                setCheckError(null);
                create.mutate(createBody(shownName, rows, columns, runIncomplete));
              })
              .catch((error: unknown) => {
                setCheckError(error);
              });
          }}
        >
          Create batch
        </Button>
      </StickyActionFooter>
    </div>
  );
}
