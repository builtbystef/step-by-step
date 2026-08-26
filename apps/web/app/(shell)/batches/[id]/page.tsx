"use client";

import {
  rerunBatchRow,
  skipBatchRow,
  takeOverRun,
  type BatchRowRecord,
  type LogLine,
  type RunStatus,
  type WorkflowDocument,
} from "@step-by-step/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { applyBatchEvent, batchIsLive, snapshotFromDetail, type BatchSnapshot } from "./events";
import { refusalMessage } from "./messages";
import {
  batchOutputTable,
  etaLabel,
  failureReasonWords,
  liveRowIndex,
  outputDownloadHref,
  progressSegments,
  rowChipState,
  rowDurationMs,
  runHref,
  stalledCallout,
  statsView,
  variableCell,
  variableColumns,
} from "./presentation";
import { batchOutputQuery, batchQuery, rowOutputQuery } from "./queries";
import { useBatchStream } from "./use-batch-stream";

import {
  applyRunEvent,
  snapshotFromDetail as snapshotFromRun,
  type CockpitSnapshot,
} from "../../runs/[id]/events";
import { chipState, clock, railItems } from "../../runs/[id]/presentation";
import { runQuery, runVersionQuery } from "../../runs/[id]/queries";
import { useRunStream } from "../../runs/[id]/use-run-stream";
import type { Step } from "../../workflows/[id]/editor/steps";
import { useActiveOrganization } from "../../use-active-organization";

import { AttributeBadge } from "@/components/primitives/attribute-badge";
import { Callout } from "@/components/primitives/callout";
import { ExpandableRow } from "@/components/primitives/expandable-row";
import { StatusChip } from "@/components/primitives/status-chip";
import { Button } from "@/components/ui/button";
import { invalidateRunState } from "@/lib/attention";
import { duration } from "@/lib/duration";
import { cn } from "@/lib/utils";

/**
 * `/batches/[id]` — the Batch as a screen: the table, the live badge, the
 * stalled callout, and the uniform Output tab.
 */

export default function BatchDetailPage() {
  const { active } = useActiveOrganization();
  const params = useParams<{ id: string }>();

  if (active === null) {
    return null;
  }

  return <BatchView orgId={active.id} batchId={params.id} />;
}

function BatchView({ orgId, batchId }: { orgId: string; batchId: string }) {
  const cache = useQueryClient();
  const router = useRouter();
  const loaded = useQuery(batchQuery(orgId, batchId));
  const [live, setLive] = useState<BatchSnapshot | null>(null);
  const [now, setNow] = useState(() => new Date());
  const [tab, setTab] = useState<"rows" | "output">("rows");
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    setLive(null);
  }, [batchId]);

  useEffect(() => {
    if (live !== null || loaded.data === undefined) {
      return;
    }
    setLive(snapshotFromDetail(loaded.data));
  }, [loaded.data, live]);

  const snapshot = live;
  const liveIndex = snapshot === null ? null : liveRowIndex(snapshot.rows);
  const liveRow = liveIndex === null || snapshot === null ? undefined : snapshot.rows[liveIndex];
  const liveRunId = liveRow?.latest_run_id ?? undefined;
  const liveRun = useQuery({
    ...runQuery(orgId, liveRunId ?? ""),
    enabled: liveRunId !== undefined,
  });
  const liveRunStatus: RunStatus | undefined = liveRun.data?.detail.run.status;
  const waiting = liveRunStatus === "waiting_for_human";
  const output = useQuery(batchOutputQuery(orgId, batchId, tab === "output"));

  useEffect(() => {
    if (snapshot === null || !batchIsLive(snapshot.rows)) {
      return;
    }
    const tick = window.setInterval(() => {
      setNow(new Date());
    }, 1000);
    return () => {
      window.clearInterval(tick);
    };
  }, [snapshot]);

  useBatchStream(
    batchId,
    snapshot !== null && batchIsLive(snapshot.rows),
    (event) => {
      setLive((current) => (current === null ? current : applyBatchEvent(current, event)));
    },
    async () => {
      const refreshed = await loaded.refetch();
      if (refreshed.data !== undefined) {
        setLive(snapshotFromDetail(refreshed.data));
      }
    },
  );

  const skip = useMutation({
    mutationFn: async (index: number) => {
      const { error } = await skipBatchRow({
        path: { batch_id: batchId, index },
      });
      if (error) throw error;
    },
    onSuccess: async () => {
      setActionError(null);
      await invalidateRunState(cache);
      const refreshed = await loaded.refetch();
      if (refreshed.data !== undefined) {
        setLive(snapshotFromDetail(refreshed.data));
      }
    },
    onError: (error) => {
      setActionError(refusalMessage(error));
    },
  });

  const rerun = useMutation({
    mutationFn: async (index: number) => {
      const { error } = await rerunBatchRow({
        path: { batch_id: batchId, index },
      });
      if (error) throw error;
    },
    onSuccess: async () => {
      setActionError(null);
      await invalidateRunState(cache);
      const refreshed = await loaded.refetch();
      if (refreshed.data !== undefined) {
        setLive(snapshotFromDetail(refreshed.data));
      }
    },
    onError: (error) => {
      setActionError(refusalMessage(error));
    },
  });

  const takeOver = useMutation({
    mutationFn: async (runId: string) => {
      const { error } = await takeOverRun({ path: { run_id: runId } });
      if (error) throw error;
      return runId;
    },
    onSuccess: async (runId) => {
      setActionError(null);
      await invalidateRunState(cache);
      router.push(runHref(runId));
    },
    onError: (error) => {
      setActionError(refusalMessage(error));
    },
  });

  if (loaded.error) {
    return <Callout tone="bad">{refusalMessage(loaded.error)}</Callout>;
  }
  if (snapshot === null) {
    return null;
  }

  const stats = statsView(snapshot.rows);
  const segments = progressSegments(snapshot.stats);
  const eta = etaLabel(snapshot.etaSeconds);
  const columns = variableColumns(snapshot.rows);
  const columnCount = 4 + columns.length;
  const callout =
    waiting && liveIndex !== null
      ? stalledCallout({
          rowIndex: liveIndex,
          queuedCount: stats.queued,
          deadlineAt: liveRun.data?.detail.run.takeover_deadline_at ?? now.toISOString(),
          now,
        })
      : null;

  return (
    <div className="flex flex-col gap-3">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-page">{snapshot.batch.name}</h1>
        <span className="font-mono text-small text-mut">{snapshot.batch.id}</span>
      </header>

      <div className="flex gap-1">
        <Tab current={tab} id="rows" onSelect={setTab}>
          Rows
        </Tab>
        <Tab current={tab} id="output" onSelect={setTab}>
          Output
        </Tab>
      </div>

      {actionError === null ? null : <Callout tone="bad">{actionError}</Callout>}

      {tab === "output" ? (
        <OutputTab assembled={output.data} error={output.error} batchId={batchId} />
      ) : (
        <>
          {callout === null || liveRunId === undefined ? null : (
            <Callout
              tone="warn"
              size="banner"
              title={callout.title}
              actions={
                <>
                  <Button
                    size="sm"
                    disabled={takeOver.isPending}
                    onClick={() => {
                      takeOver.mutate(liveRunId);
                    }}
                  >
                    {callout.takeOver}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={skip.isPending}
                    onClick={() => {
                      skip.mutate(liveIndex ?? 0);
                    }}
                  >
                    {callout.skip}
                  </Button>
                </>
              }
            >
              <p>{callout.sequential}</p>
              <p>
                <span className="font-mono">{callout.countdown}</span>
                {" — "}
                {callout.timeout}
              </p>
            </Callout>
          )}

          <StatsHeader stats={stats} segments={segments} eta={eta} />

          <div className="overflow-auto">
            <table className="w-full text-left text-half">
              <thead>
                <tr className="text-micro text-mut">
                  <th className="w-8" />
                  <th className="px-2 py-1 font-semibold">#</th>
                  {columns.map((column) => (
                    <th key={column} className="px-2 py-1 font-semibold">
                      {column}
                    </th>
                  ))}
                  <th className="px-2 py-1 font-semibold">status</th>
                  <th className="px-2 py-1 font-semibold">duration</th>
                  <th className="px-2 py-1 font-semibold" />
                </tr>
              </thead>
              {snapshot.rows.map((row) => (
                <Row
                  key={row.index}
                  orgId={orgId}
                  row={row}
                  columns={columns}
                  columnCount={columnCount}
                  now={now}
                  live={liveIndex === row.index}
                  liveRunStatus={liveIndex === row.index ? liveRunStatus : undefined}
                  onRerun={() => {
                    rerun.mutate(row.index);
                  }}
                  rerunning={rerun.isPending}
                />
              ))}
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function StatsHeader({
  stats,
  segments,
  eta,
}: {
  stats: ReturnType<typeof statsView>;
  segments: ReturnType<typeof progressSegments>;
  eta: string | null;
}) {
  const total = Math.max(
    1,
    segments.reduce((sum, segment) => sum + segment.count, 0),
  );
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-x-5 gap-y-1 text-small text-mut">
        <span>
          done{" "}
          <span className="font-semibold text-ink">
            {String(stats.done)}/{String(stats.total)}
          </span>
        </span>
        <span>
          succeeded <span className="font-semibold text-ink">{String(stats.succeeded)}</span>
        </span>
        <span>
          failed <span className="font-semibold text-ink">{String(stats.failed)}</span>
        </span>
        <span>
          queued <span className="font-semibold text-ink">{String(stats.queued)}</span>
        </span>
        <span>
          skipped <span className="font-semibold text-ink">{String(stats.skipped)}</span>
        </span>
        {eta === null ? null : <span className="ml-auto font-mono text-ink">{eta}</span>}
      </div>
      <div className="flex h-2 overflow-hidden rounded-full border border-line">
        {segments.map((segment) =>
          segment.count === 0 ? null : (
            <div
              key={segment.key}
              title={`${segment.key} · ${String(segment.count)}`}
              className={cn("min-w-0", SEGMENT_TONE[segment.tone])}
              style={{ flex: segment.count / total }}
            />
          ),
        )}
      </div>
    </div>
  );
}

const SEGMENT_TONE: Record<ReturnType<typeof progressSegments>[number]["tone"], string> = {
  ok: "bg-ok",
  bad: "bg-bad",
  accent: "bg-accent",
  neutral: "bg-muted-foreground/40",
  muted: "bg-muted",
};

function Row({
  orgId,
  row,
  columns,
  columnCount,
  now,
  live,
  liveRunStatus,
  onRerun,
  rerunning,
}: {
  orgId: string;
  row: BatchRowRecord;
  columns: string[];
  columnCount: number;
  now: Date;
  live: boolean;
  liveRunStatus: RunStatus | undefined;
  onRerun: () => void;
  rerunning: boolean;
}) {
  const elapsed = rowDurationMs(row, now);
  return (
    <ExpandableRow
      columnCount={columnCount}
      expandLabel={`Expand row ${String(row.index + 1)}`}
      defaultOpen={live || row.status === "failed"}
      cells={
        <>
          <td className="px-2 py-1 font-mono text-micro">{String(row.index + 1)}</td>
          {columns.map((column) => (
            <td key={column} className="px-2 py-1 font-mono text-micro">
              {variableCell(row.variables[column])}
            </td>
          ))}
          <td className="px-2 py-1">
            <StatusChip state={rowChipState(row, liveRunStatus)} />
          </td>
          <td className="px-2 py-1 font-mono text-micro text-mut">
            {elapsed === null ? "" : duration(elapsed)}
          </td>
          <td className="px-2 py-1">
            {live ? <AttributeBadge tone="accent">live</AttributeBadge> : null}
          </td>
        </>
      }
    >
      {live && row.latest_run_id !== null ? (
        <LiveExpansion orgId={orgId} runId={row.latest_run_id} />
      ) : row.status === "failed" ? (
        <FailedExpansion row={row} onRerun={onRerun} rerunning={rerunning} />
      ) : row.status === "succeeded" && row.latest_run_id !== null ? (
        <SucceededExpansion orgId={orgId} runId={row.latest_run_id} />
      ) : (
        <p className="text-mut">This row has not run yet.</p>
      )}
    </ExpandableRow>
  );
}

function FailedExpansion({
  row,
  onRerun,
  rerunning,
}: {
  row: BatchRowRecord;
  onRerun: () => void;
  rerunning: boolean;
}) {
  const latest = row.runs[row.runs.length - 1];
  const runId = row.latest_run_id;
  return (
    <div className="flex flex-col gap-2">
      <p>{failureReasonWords(latest?.failure_reason ?? null)}</p>
      <div className="flex gap-2">
        {runId === null ? null : (
          <Button size="sm" variant="outline" render={<Link href={runHref(runId)} />}>
            Open the run
          </Button>
        )}
        <Button size="sm" disabled={rerunning} onClick={onRerun}>
          Re-run just this row
        </Button>
      </div>
    </div>
  );
}

function SucceededExpansion({ orgId, runId }: { orgId: string; runId: string }) {
  const output = useQuery(rowOutputQuery(orgId, runId, true));
  const table = output.data === undefined ? null : batchOutputTable(coerceRunOutput(output.data));
  return (
    <div className="flex flex-col gap-2">
      <Link className="text-small font-semibold text-accent" href={runHref(runId)}>
        Open the run
      </Link>
      {table === null ? (
        <p className="text-mut">This row extracted no data.</p>
      ) : (
        <OutputGrid table={table} />
      )}
    </div>
  );
}

function coerceRunOutput(assembled: unknown): unknown {
  if (Array.isArray(assembled) && assembled.every(isPlainObject)) {
    const columns: string[] = [];
    const seen = new Set<string>();
    for (const row of assembled) {
      for (const key of Object.keys(row)) {
        if (!seen.has(key)) {
          seen.add(key);
          columns.push(key);
        }
      }
    }
    return {
      columns,
      rows: assembled.map((row) => columns.map((column) => row[column])),
    };
  }
  if (isPlainObject(assembled) && !Array.isArray(assembled.columns)) {
    const columns = Object.keys(assembled);
    return { columns, rows: [columns.map((column) => assembled[column])] };
  }
  return assembled;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function LiveExpansion({ orgId, runId }: { orgId: string; runId: string }) {
  const loaded = useQuery(runQuery(orgId, runId));
  const [live, setLive] = useState<CockpitSnapshot | null>(null);
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    setLive(null);
  }, [runId]);

  useEffect(() => {
    if (live !== null || loaded.data === undefined) {
      return;
    }
    setLive(snapshotFromRun(loaded.data.detail, loaded.data.logs));
  }, [loaded.data, live]);

  useEffect(() => {
    const tick = window.setInterval(() => {
      setNow(new Date());
    }, 1000);
    return () => {
      window.clearInterval(tick);
    };
  }, []);

  useRunStream(
    runId,
    live?.run.status,
    (event) => {
      setLive((current) => (current === null ? current : applyRunEvent(current, event)));
    },
    async () => {
      const refreshed = await loaded.refetch();
      if (refreshed.data !== undefined) {
        setLive(snapshotFromRun(refreshed.data.detail, refreshed.data.logs));
      }
    },
  );

  const version = useQuery(
    runVersionQuery(
      orgId,
      live?.run.workflow_id ?? "",
      live?.run.version_number ?? null,
      live !== null && live.run.draft_snapshot === null,
    ),
  );

  if (live === null) {
    return <p className="text-mut">Loading this row&rsquo;s Run…</p>;
  }

  const document = (version.data ?? { steps: [] }) as WorkflowDocument;
  const steps: Step[] = document.steps ?? [];
  const rail = railItems({
    steps,
    results: live.stepResults,
    artifacts: live.artifacts,
    intervals: live.intervals,
    inFlight: live.inFlight,
    now,
  });
  const tail = live.logs.slice(-8);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <StatusChip state={chipState(live.run)} />
        <Link className="text-small font-semibold text-accent" href={runHref(runId)}>
          Open the full run
        </Link>
      </div>
      <ol className="flex flex-col gap-0.5">
        {rail.map((item) =>
          item.kind === "control" ? (
            <li key={`${item.phase}-${item.label}`} className="text-small text-mut">
              {item.label}
            </li>
          ) : (
            <li key={item.step.id} className="flex gap-2 text-small">
              <span className="w-6 text-mut">{String(item.position + 1)}</span>
              <span className="font-semibold">{item.step.label}</span>
              <span className="ml-auto font-mono text-micro text-mut">
                {item.durationMs === null ? (item.inFlight ? "…" : "") : clock(item.durationMs)}
              </span>
            </li>
          ),
        )}
      </ol>
      <LogTail logs={tail} origin={live.run.started_at ?? live.run.queued_at} />
    </div>
  );
}

function LogTail({ logs, origin }: { logs: LogLine[]; origin: string }) {
  if (logs.length === 0) {
    return <p className="text-mut">No log lines yet.</p>;
  }
  const start = Date.parse(origin);
  return (
    <ol className="flex max-h-40 flex-col gap-0.5 overflow-auto font-mono text-micro">
      {logs.map((line) => (
        <li key={line.seq} className="flex gap-2">
          <span className="w-10 shrink-0 text-mut">
            {Number.isNaN(start) ? "" : clock(Date.parse(line.at) - start)}
          </span>
          <span>{line.text}</span>
        </li>
      ))}
    </ol>
  );
}

function OutputTab({
  assembled,
  error,
  batchId,
}: {
  assembled: unknown;
  error: unknown;
  batchId: string;
}) {
  if (error) {
    return <Callout tone="bad">{refusalMessage(error)}</Callout>;
  }
  if (assembled === undefined) {
    return null;
  }
  const table = batchOutputTable(assembled);
  if (table === null) {
    return <p className="text-half text-mut">This Batch has no output yet.</p>;
  }
  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-3">
        <a
          className="text-small font-semibold text-accent"
          href={outputDownloadHref(batchId, "json")}
          download="batch.json"
        >
          Download JSON
        </a>
        <a
          className="text-small font-semibold text-accent"
          href={outputDownloadHref(batchId, "csv")}
          download="batch.csv"
        >
          Download CSV
        </a>
      </div>
      <OutputGrid table={table} />
    </div>
  );
}

function OutputGrid({ table }: { table: { columns: string[]; rows: string[][] } }) {
  return (
    <div className="max-h-96 overflow-auto">
      <table className="w-full text-left text-half">
        <thead>
          <tr>
            {table.columns.map((column) => (
              <th key={column} className="border-b border-line px-2 py-1 font-semibold text-mut">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, index) => (
            <tr key={row.join("\u0001") + String(index)}>
              {row.map((cell, cellIndex) => (
                <td
                  key={`${table.columns[cellIndex] ?? String(cellIndex)}-${cell}`}
                  className="border-b border-line px-2 py-1 font-mono text-micro"
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Tab({
  current,
  id,
  onSelect,
  children,
}: {
  current: "rows" | "output";
  id: "rows" | "output";
  onSelect: (id: "rows" | "output") => void;
  children: string;
}) {
  return (
    <button
      type="button"
      className={cn(
        "rounded-md px-2 py-1 text-small",
        current === id ? "bg-accent-bg font-semibold text-accent" : "text-mut hover:text-ink",
      )}
      onClick={() => {
        onSelect(id);
      }}
    >
      {children}
    </button>
  );
}
