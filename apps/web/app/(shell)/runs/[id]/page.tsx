"use client";

import {
  cancelRun,
  downloadRunArtifact,
  type ArtifactRecord,
  type AuthStateConsentScope,
  type LogLine,
  type RunControlKind,
  type Variable,
  type WorkflowDocument,
} from "@step-by-step/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { applyRunEvent, snapshotFromDetail, type CockpitSnapshot } from "./events";
import { refusalMessage } from "./messages";
import { currentPhase, waitingStep } from "./pane";
import { PanePanel } from "./pane-panel";
import {
  CANCEL_CONFIRM,
  cancellingBand,
  chipState,
  clock,
  currentStepNumber,
  driftChipLabel,
  driftedCount,
  elapsedMs,
  isTerminal,
  offersRepick,
  railItems,
  stepsDoneLabel,
  stepExpansion,
  terminalBanner,
  timeWithYouMs,
  timeline,
  triggerLabel,
  versionLabel,
} from "./presentation";
import { runQuery, runVersionQuery, runWorkflowQuery } from "./queries";
import { RunAgainDialog } from "./run-again-dialog";
import { useRunStream } from "./use-run-stream";
import { useTakeoverLock } from "./use-takeover-lock";

import { Sentence } from "../../workflows/[id]/editor/sentence";
import type { Step } from "../../workflows/[id]/editor/steps";
import { summarize } from "../../workflows/[id]/editor/summary";
import { secretNames } from "../../workflows/[id]/editor/variables";
import { useActiveOrganization } from "../../use-active-organization";

import { AttributeBadge } from "@/components/primitives/attribute-badge";
import { Callout } from "@/components/primitives/callout";
import { StatusChip } from "@/components/primitives/status-chip";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { invalidateRunState } from "@/lib/attention";
import { duration } from "@/lib/duration";
import { cn } from "@/lib/utils";

/**
 * `/runs/[id]` — the cockpit where a Run is understood.
 *
 * The pane is the Worker's browser: view-only while automation runs,
 * amber and waiting when parked, interactive during takeover.
 */

export default function RunDetailPage() {
  const { active } = useActiveOrganization();
  const params = useParams<{ id: string }>();

  if (active === null) {
    return null;
  }

  return <Cockpit orgId={active.id} runId={params.id} />;
}

function Cockpit({ orgId, runId }: { orgId: string; runId: string }) {
  const cache = useQueryClient();
  const loaded = useQuery(runQuery(orgId, runId));
  const [live, setLive] = useState<CockpitSnapshot | null>(null);
  const [now, setNow] = useState(() => new Date());
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const [runAgain, setRunAgain] = useState(false);
  const [drawer, setDrawer] = useState<"logs" | "artifacts">("logs");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [weHoldControl, setWeHoldControl] = useState(false);
  const [unmetHandback, setUnmetHandback] = useState(false);
  const [alreadyHeld, setAlreadyHeld] = useState(false);
  const pendingHandback = useRef(false);
  const lock = useTakeoverLock(runId);

  useEffect(() => {
    setLive(null);
  }, [runId]);

  useEffect(() => {
    if (live !== null || loaded.data === undefined) {
      return;
    }
    setLive(snapshotFromDetail(loaded.data.detail, loaded.data.logs));
  }, [loaded.data, live]);

  const snapshot = live;
  const status = snapshot?.run.status;
  const cancelling =
    snapshot !== null &&
    chipState(snapshot.run) === "cancelling" &&
    !isTerminal(snapshot.run.status);

  useEffect(() => {
    if (status === undefined || isTerminal(status)) {
      return;
    }
    const tick = window.setInterval(() => {
      setNow(new Date());
    }, 1000);
    return () => {
      window.clearInterval(tick);
    };
  }, [status]);

  const pullCandidates = async () => {
    const refreshed = await loaded.refetch();
    const candidates = refreshed.data?.detail.auth_state_candidates;
    if (candidates === undefined) {
      return;
    }
    setLive((current) =>
      current === null ? current : { ...current, authStateCandidates: candidates },
    );
  };

  useRunStream(
    runId,
    status,
    (event) => {
      if (event.type === "control" && pendingHandback.current) {
        if (event.data.phase === "waiting") {
          setUnmetHandback(true);
          pendingHandback.current = false;
          void pullCandidates();
        }
        if (event.data.phase === "automation") {
          pendingHandback.current = false;
          void pullCandidates();
        }
      }
      setLive((current) => (current === null ? current : applyRunEvent(current, event)));
    },
    async () => {
      const refreshed = await loaded.refetch();
      if (refreshed.data !== undefined) {
        setLive(snapshotFromDetail(refreshed.data.detail, refreshed.data.logs));
      }
    },
  );

  useEffect(() => {
    if (status !== "waiting_for_human") {
      setWeHoldControl(false);
      setUnmetHandback(false);
      setAlreadyHeld(false);
    }
  }, [status]);

  const releaseHold = lock.release;
  const releaseHoldRef = useRef(releaseHold);
  releaseHoldRef.current = releaseHold;
  useEffect(() => {
    return () => {
      releaseHoldRef.current();
    };
  }, [runId]);

  const workflowId = snapshot?.run.workflow_id ?? "";
  const workflow = useQuery(runWorkflowQuery(orgId, workflowId, workflowId !== ""));
  const version = useQuery(
    runVersionQuery(
      orgId,
      workflowId,
      snapshot?.run.version_number ?? null,
      snapshot !== null && snapshot.run.draft_snapshot === null,
    ),
  );

  const cancel = useMutation({
    mutationFn: async () => {
      const { error } = await cancelRun({ path: { run_id: runId } });
      if (error) throw error;
    },
    onSuccess: async () => {
      setConfirmingCancel(false);
      await invalidateRunState(cache);
      const refreshed = await loaded.refetch();
      if (refreshed.data !== undefined) {
        setLive(snapshotFromDetail(refreshed.data.detail, refreshed.data.logs));
      }
    },
  });

  if (loaded.error) {
    return <Callout tone="bad">{refusalMessage(loaded.error)}</Callout>;
  }
  if (snapshot === null) {
    return null;
  }

  const document = documentOf(snapshot.run.draft_snapshot, version.data);
  const steps: Step[] = document.steps ?? [];
  const secrets = secretNames(document);
  const variables: Variable[] = document.variables ?? [];
  const banner = terminalBanner({
    run: snapshot.run,
    results: snapshot.stepResults,
    artifacts: snapshot.artifacts,
    totalSteps: steps.length,
  });
  const drift = driftChipLabel(driftedCount(snapshot.stepResults));
  const strip = timeline(snapshot.intervals, now);
  const rail = railItems({
    steps,
    results: snapshot.stepResults,
    artifacts: snapshot.artifacts,
    intervals: snapshot.intervals,
    inFlight: snapshot.inFlight,
    now,
  });
  const failed = snapshot.stepResults.find((result) => result.status === "failed");
  const failedStep = steps.find((step) => step.id === failed?.step_id);

  return (
    <div className="flex flex-col gap-3">
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-page">{workflow.data?.name ?? "Run"}</h1>
          <span className="font-mono text-small text-mut">{snapshot.run.id}</span>
          <span className="text-small text-mut">{versionLabel(snapshot.run)}</span>
          <span className="text-small text-mut">{triggerLabel(snapshot.run.trigger)}</span>
          <StatusChip state={chipState(snapshot.run)} />
          {drift === null ? null : <AttributeBadge tone="wait">{drift}</AttributeBadge>}
          <div className="ml-auto flex items-center gap-2">
            {isTerminal(snapshot.run.status) ? (
              <Button
                size="sm"
                onClick={() => {
                  setRunAgain(true);
                }}
              >
                Run again
              </Button>
            ) : confirmingCancel ? null : (
              <Button
                size="sm"
                variant="destructive"
                onClick={() => {
                  setConfirmingCancel(true);
                }}
              >
                Cancel run
              </Button>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-x-5 gap-y-1 text-small text-mut">
          <Meta label="elapsed" value={clock(elapsedMs(snapshot.run, now))} />
          <Meta label="automation" value={clock(snapshot.run.automation_ms)} />
          <Meta label="time with you" value={clock(timeWithYouMs(snapshot.intervals, now))} />
          <Meta label="steps done" value={stepsDoneLabel(snapshot.stepResults, steps.length)} />
          <Meta label="worker" value={snapshot.run.worker_id ?? "—"} />
          <Meta label="timeout" value={duration(snapshot.run.timeout_ms)} />
          {snapshot.run.failure_reason === null || !isTerminal(snapshot.run.status) ? null : (
            <Meta label="failure_reason" value={snapshot.run.failure_reason} />
          )}
        </div>
      </header>

      <TimelineStrip strip={strip} />

      {confirmingCancel && !cancelling && banner === null ? (
        <Callout
          tone="warn"
          size="banner"
          title="Cancel this Run?"
          actions={
            <>
              <Button
                size="sm"
                variant="destructive"
                disabled={cancel.isPending}
                onClick={() => {
                  cancel.mutate();
                }}
              >
                Cancel run
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setConfirmingCancel(false);
                }}
              >
                Keep running
              </Button>
            </>
          }
        >
          {CANCEL_CONFIRM}
        </Callout>
      ) : null}

      {cancel.error ? <Callout tone="bad">{refusalMessage(cancel.error)}</Callout> : null}

      <div className="grid gap-3 lg:grid-cols-[minmax(16rem,22rem)_1fr]">
        <Card className="min-h-64 py-0">
          <CardContent className="flex flex-col gap-1 p-2">
            {rail.map((item, index) =>
              item.kind === "control" ? (
                <ControlBand key={`band-${String(index)}`} item={item} />
              ) : (
                <StepRow
                  key={item.step.id}
                  item={item}
                  runId={runId}
                  workflowId={workflowId}
                  secrets={secrets}
                  artifacts={snapshot.artifacts}
                  logs={snapshot.logs}
                  open={expanded === item.step.id}
                  onOpenChange={(open) => {
                    setExpanded(open ? item.step.id : null);
                  }}
                />
              ),
            )}
          </CardContent>
        </Card>

        <Card className="min-h-64 py-0">
          <CardContent className="flex flex-col gap-3 p-4">
            {cancelling ? (
              <Callout tone="info" size="banner">
                {cancellingBand(currentStepNumber(snapshot.inFlight, snapshot.stepResults))}
              </Callout>
            ) : null}
            {banner === null ? null : (
              <Callout
                tone={
                  snapshot.run.status === "succeeded"
                    ? "ok"
                    : snapshot.run.status === "failed"
                      ? "bad"
                      : "info"
                }
                size="banner"
                actions={
                  snapshot.run.status === "failed" &&
                  offersRepick(snapshot.run, snapshot.stepResults) &&
                  failedStep !== undefined ? (
                    <Link
                      href={`/workflows/${workflowId}/editor?repick=${failedStep.id}`}
                      className="text-small font-semibold text-accent"
                    >
                      Re-pick the element
                    </Link>
                  ) : null
                }
              >
                {banner}
              </Callout>
            )}
            <PanePanel
              runId={runId}
              status={snapshot.run.status}
              cancelling={cancelling}
              phase={currentPhase(snapshot.intervals)}
              workerId={snapshot.run.worker_id}
              trigger={snapshot.run.trigger}
              deadlineAt={snapshot.run.takeover_deadline_at}
              pauseRequested={snapshot.run.pause_requested_at !== null}
              autoHandbackDisabled={snapshot.run.auto_handback_disabled}
              pause={waitingStep(steps, snapshot.stepResults, snapshot.inFlight)}
              predicate={snapshot.predicate}
              diagnostics={snapshot.diagnostics}
              candidates={snapshot.authStateCandidates}
              weHoldControl={weHoldControl}
              heldElsewhere={lock.heldElsewhere || alreadyHeld}
              unmetHandback={unmetHandback}
              now={now}
              onTookOver={() => {
                setAlreadyHeld(false);
                setUnmetHandback(false);
                setWeHoldControl(true);
                lock.claim();
              }}
              onReleased={() => {
                pendingHandback.current = weHoldControl;
                setWeHoldControl(false);
                lock.release();
              }}
              onUnmet={() => {
                setUnmetHandback(false);
              }}
              onStay={() => {
                setLive((current) =>
                  current === null
                    ? current
                    : {
                        ...current,
                        run: { ...current.run, auto_handback_disabled: true },
                      },
                );
              }}
              onPause={() => {
                setLive((current) =>
                  current === null
                    ? current
                    : {
                        ...current,
                        run: {
                          ...current.run,
                          pause_requested_at:
                            current.run.pause_requested_at ?? new Date().toISOString(),
                        },
                      },
                );
              }}
              onConsented={(domain: string, scope: AuthStateConsentScope) => {
                setLive((current) =>
                  current === null
                    ? current
                    : {
                        ...current,
                        authStateCandidates: current.authStateCandidates.map((candidate) =>
                          candidate.domain === domain
                            ? { ...candidate, consent: { scope } }
                            : candidate,
                        ),
                      },
                );
              }}
              onCancel={() => {
                setConfirmingCancel(true);
              }}
              onError={(error) => {
                if (errorCode(error) === "already_held") {
                  setAlreadyHeld(true);
                }
              }}
            />
          </CardContent>
        </Card>
      </div>

      <Card className="py-0">
        <CardContent className="p-3">
          <div className="mb-2 flex gap-1">
            <DrawerTab current={drawer} id="logs" onSelect={setDrawer}>
              Logs
            </DrawerTab>
            <DrawerTab current={drawer} id="artifacts" onSelect={setDrawer}>
              Artifacts
            </DrawerTab>
          </div>
          {drawer === "logs" ? (
            <LogList
              logs={snapshot.logs}
              origin={snapshot.run.started_at ?? snapshot.run.queued_at}
            />
          ) : (
            <ArtifactList runId={runId} artifacts={snapshot.artifacts} />
          )}
        </CardContent>
      </Card>

      <RunAgainDialog
        open={runAgain}
        workflowId={workflowId}
        declared={variables}
        stored={snapshot.run.variables}
        onOpenChange={setRunAgain}
      />
    </div>
  );
}

function documentOf(
  snapshot: RunRecordDraft,
  published: WorkflowDocument | undefined,
): WorkflowDocument {
  if (snapshot !== null && typeof snapshot === "object") {
    return snapshot as WorkflowDocument;
  }
  return published ?? { steps: [], variables: [] };
}

type RunRecordDraft = WorkflowDocument | { [key: string]: unknown } | null;

function errorCode(error: unknown): string | undefined {
  if (typeof error === "object" && error !== null && "code" in error) {
    return typeof error.code === "string" ? error.code : undefined;
  }
  return undefined;
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <span>
      {label} <span className="font-semibold text-ink">{value}</span>
    </span>
  );
}

const KIND_CLASS: Record<RunControlKind, string> = {
  automation: "bg-accent",
  waiting: "bg-wait bg-[repeating-linear-gradient(45deg,transparent_0_4px,var(--panel)_4px_8px)]",
  human: "bg-human",
  verifying: "bg-[repeating-linear-gradient(90deg,var(--accent)_0_4px,var(--accent-bg)_4px_8px)]",
};

function TimelineStrip({ strip }: { strip: ReturnType<typeof timeline> }) {
  if (strip.segments.length === 0) {
    return null;
  }
  return (
    <div className="flex flex-col gap-1">
      <div className="flex h-5 overflow-hidden rounded-md border border-line">
        {strip.segments.map((segment, index) => (
          <div
            key={`${segment.kind}-${String(index)}`}
            title={`${segment.kind} · ${clock(segment.durationMs)}`}
            className={cn("min-w-1", KIND_CLASS[segment.kind])}
            style={{ flex: segment.flex }}
          />
        ))}
      </div>
      <div className="relative h-5">
        {strip.markers.map((marker) => (
          <span
            key={`${marker.label}-${String(marker.at)}`}
            className="absolute -translate-x-1/2 text-micro text-mut"
            style={{ left: `${String(marker.at * 100)}%` }}
          >
            {marker.label}
          </span>
        ))}
      </div>
      <div className="flex flex-wrap gap-3 text-micro text-mut">
        <LegendSwatch className={KIND_CLASS.automation} label="automation" />
        <LegendSwatch className={KIND_CLASS.waiting} label="waiting for you" />
        <LegendSwatch className={KIND_CLASS.human} label="you in control" />
        <LegendSwatch className={KIND_CLASS.verifying} label="verifying" />
      </div>
    </div>
  );
}

function LegendSwatch({ className, label }: { className: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <i className={cn("inline-block size-2.5 rounded-sm", className)} />
      {label}
    </span>
  );
}

function ControlBand({
  item,
}: {
  item: Extract<ReturnType<typeof railItems>[number], { kind: "control" }>;
}) {
  const tone =
    item.phase === "waiting"
      ? "border-wait/30 bg-wait-bg text-wait"
      : item.phase === "human"
        ? "border-human/30 bg-human-bg text-human"
        : "border-accent/30 bg-accent-bg text-accent";
  return <div className={cn("rounded-md border px-2 py-1 text-small", tone)}>{item.label}</div>;
}

function StepRow({
  item,
  runId,
  workflowId,
  secrets,
  artifacts,
  logs,
  open,
  onOpenChange,
}: {
  item: Extract<ReturnType<typeof railItems>[number], { kind: "step" }>;
  runId: string;
  workflowId: string;
  secrets: ReadonlySet<string>;
  artifacts: ArtifactRecord[];
  logs: LogLine[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const expansion = stepExpansion({
    workflowId,
    step: item.step,
    result: item.result,
    artifacts,
    logs,
  });
  return (
    <Collapsible open={open} onOpenChange={onOpenChange} className="rounded-md">
      <CollapsibleTrigger className="flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left hover:bg-muted">
        <ChevronRight
          aria-hidden
          className={cn(
            "mt-0.5 size-4 shrink-0 text-mut transition-transform",
            open && "rotate-90",
          )}
        />
        <span className="w-6 shrink-0 text-small text-mut">{String(item.position + 1)}</span>
        <span className="min-w-0 flex-1">
          <span className="block font-semibold">{item.step.label}</span>
          <Sentence segments={summarize(item.step)} secrets={secrets} />
        </span>
        <span className="shrink-0 font-mono text-micro text-mut">
          {item.durationMs === null ? (item.inFlight ? "…" : "") : clock(item.durationMs)}
        </span>
      </CollapsibleTrigger>
      {item.badges.length === 0 ? null : (
        <div className="ml-12 flex flex-wrap gap-1 pb-1">
          {item.badges.map((badge) => (
            <AttributeBadge key={badge.key} tone={badge.tone}>
              {badge.label}
            </AttributeBadge>
          ))}
        </div>
      )}
      <CollapsibleContent className="ml-12 flex flex-col gap-2 pb-2 text-half">
        {expansion.error === null ? null : (
          <Callout tone="bad" title={expansion.error.code}>
            {expansion.error.message}
          </Callout>
        )}
        {expansion.candidates.length === 0 ? null : (
          <div className="rounded-md border border-wait/30 bg-wait-bg p-2 text-wait">
            <p className="font-semibold">Selector Drift</p>
            <ol className="mt-1 list-decimal pl-4">
              {expansion.candidates.map((candidate, index) => (
                <li key={`${candidate.kind}-${String(index)}`}>
                  <span className="font-mono text-small text-ink">{candidate.value}</span>
                  <span className="ml-2 text-micro">
                    {candidate.fate === "matched"
                      ? "matched"
                      : candidate.fate === "died"
                        ? "died"
                        : "not tried"}
                  </span>
                </li>
              ))}
            </ol>
            {expansion.repickHref === null ? null : (
              <Link className="mt-1 inline-block text-accent" href={expansion.repickHref}>
                Re-pick in the editor
              </Link>
            )}
          </div>
        )}
        {expansion.screenshots.map((shot) => (
          <FailureShot key={shot.id} runId={runId} artifact={shot} />
        ))}
        {expansion.extracted === null ? null : (
          <pre className="overflow-auto rounded-md bg-muted p-2 font-mono text-micro">
            {JSON.stringify(expansion.extracted, null, 2)}
          </pre>
        )}
        {expansion.logs.length === 0 ? null : (
          <LogList
            logs={expansion.logs}
            origin={item.result?.started_at ?? expansion.logs[0]?.at ?? ""}
          />
        )}
      </CollapsibleContent>
    </Collapsible>
  );
}

function FailureShot({ runId, artifact }: { runId: string; artifact: ArtifactRecord }) {
  const url = useQuery({
    queryKey: ["artifact-location", runId, artifact.id],
    queryFn: async (): Promise<string> => {
      const fallback = `/api/runs/${runId}/artifacts/${artifact.id}/download`;
      const { response } = await downloadRunArtifact({
        path: { run_id: runId, artifact_id: artifact.id },
        redirect: "manual",
      });
      return response?.headers.get("Location") ?? fallback;
    },
  });
  if (url.data === undefined) {
    return <p className="text-micro text-mut">{artifact.filename}</p>;
  }
  return (
    <img
      src={url.data}
      alt={artifact.filename}
      className="max-h-64 rounded-md border border-line"
    />
  );
}

function DrawerTab({
  current,
  id,
  onSelect,
  children,
}: {
  current: "logs" | "artifacts";
  id: "logs" | "artifacts";
  onSelect: (id: "logs" | "artifacts") => void;
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

function LogList({ logs, origin }: { logs: LogLine[]; origin: string }) {
  if (logs.length === 0) {
    return <p className="text-half text-mut">No log lines yet.</p>;
  }
  const start = Date.parse(origin);
  return (
    <ol className="flex max-h-64 flex-col gap-0.5 overflow-auto font-mono text-micro">
      {logs.map((line) => (
        <li key={line.seq} className="flex gap-2">
          <span className="w-10 shrink-0 text-mut">
            {Number.isNaN(start) ? "" : clock(Date.parse(line.at) - start)}
          </span>
          <span className={line.level === "error" ? "text-bad" : undefined}>{line.text}</span>
        </li>
      ))}
    </ol>
  );
}

function ArtifactList({ runId, artifacts }: { runId: string; artifacts: ArtifactRecord[] }) {
  if (artifacts.length === 0) {
    return <p className="text-half text-mut">No Artifacts yet.</p>;
  }
  return (
    <ul className="flex flex-col gap-1 text-half">
      {artifacts.map((artifact) => (
        <li key={artifact.id} className="flex items-center gap-2">
          <AttributeBadge tone="neutral">{artifact.kind}</AttributeBadge>
          <a className="text-accent" href={`/api/runs/${runId}/artifacts/${artifact.id}/download`}>
            {artifact.filename}
          </a>
        </li>
      ))}
    </ul>
  );
}
