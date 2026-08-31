"use client";

import {
  createRecordingSession,
  finalizeRecordingSession,
  restoreWorkflowVersion,
  saveWorkflowDraft,
  type SelectorCandidate,
  type Variable,
  type WorkflowDocument,
} from "@step-by-step/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Braces, History, Play, Plus } from "lucide-react";
import Link from "next/link";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { withStepAdded, withStepDeleted, withStepMoved, withStepReplaced } from "./edits";
import { LEAVE_PROMPT, shouldAskBeforeLeave } from "./leave";
import { readRefusal, saveRefusal } from "./messages";
import { repairFromDrift } from "./drift";
import { draftKey, draftQuery, selectorDriftQuery, versionDocumentQuery } from "./queries";
import { RepickDialog } from "./repick-dialog";
import { RestoreDialog } from "./restore-dialog";
import { repickRefusal } from "./selectors";
import { StepCard } from "./step-card";
import { TestRunDialog } from "./test-run-dialog";
import { testRunFields, testRunRefusal } from "./test-run";
import { ADDABLE_STEP_TYPES, STEP_TYPE_LABELS, blankStep, targetsOf, type Step } from "./steps";
import { VariablesDrawer } from "./variables-drawer";
import {
  secretNames,
  undeclaredRows,
  variableRows,
  withLiteralMadeVariable,
  type Span,
} from "./variables";

import { workflowKey, workflowQuery } from "../queries";
import { restoreConsequence, versionPath, viewedVersion } from "../versions";

import { workflowsKey } from "../../queries";

import { useActiveOrganization } from "../../../use-active-organization";
import { loadSecrets, SECRETS_KEY } from "../../../settings/secrets/queries";

import { InstallAndConnect } from "@/components/extension/install-and-connect";
import { Callout } from "@/components/primitives/callout";
import { CountBadge } from "@/components/primitives/count-badge";
import { EmptyState } from "@/components/primitives/empty-state";
import { StickyActionFooter } from "@/components/primitives/sticky-action-footer";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useExtensionConnection } from "@/lib/extension-connection-context";
import {
  RECORDING_FINISHED,
  RECORDING_TOKEN_EXPIRED,
  REPICK_CANDIDATES,
  readExtensionMessage,
  recordingPendingMessage,
  recordingTokenMessage,
  repickPendingMessage,
} from "@/lib/extension-protocol";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export default function EditorTab() {
  const { active } = useActiveOrganization();
  const params = useParams<{ id: string }>();

  if (active === null) {
    return null;
  }

  return <DraftEditor orgId={active.id} workflowId={params.id} />;
}

function DraftEditor({ orgId, workflowId }: { orgId: string; workflowId: string }) {
  const connection = useExtensionConnection();
  const cache = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const viewing = viewedVersion(searchParams.get("version"));
  const draft = useQuery(draftQuery(orgId, workflowId));
  const version = useQuery(versionDocumentQuery(orgId, workflowId, viewing));
  const workflow = useQuery(workflowQuery(orgId, workflowId));
  const drift = useQuery(selectorDriftQuery(orgId, workflowId));
  const vault = useQuery({ queryKey: SECRETS_KEY, queryFn: loadSecrets });
  const [edited, setEdited] = useState<WorkflowDocument | null>(null);
  const unsaved = edited !== null;
  const query = searchParams.toString();
  const here = query === "" ? pathname : `${pathname}?${query}`;
  const [expanded, setExpanded] = useState<string | null>(null);
  const [repairing, setRepairing] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const [highlighted, setHighlighted] = useState<string | null>(null);
  const [restoring, setRestoring] = useState<number | null>(null);
  const [recordingNote, setRecordingNote] = useState<string | null>(null);
  const [repick, setRepick] = useState<{
    sessionId: string;
    token: string;
    stepId: string;
    old: SelectorCandidate[];
    next: SelectorCandidate[] | null;
  } | null>(null);

  const recording = useMutation({
    mutationFn: async (document: WorkflowDocument) => {
      if (connection.version === null || workflow.data === undefined) {
        throw new Error("The connected extension is not ready.");
      }
      const availableSecrets = vault.data ?? (await loadSecrets());
      const { data, error } = await createRecordingSession({
        path: { workflow_id: workflowId },
        headers: { "X-Extension-Version": connection.version },
        body: { mode: "record" },
      });
      if (error) throw error;
      window.postMessage(
        recordingPendingMessage({
          sessionId: data.session_id,
          token: data.token,
          backendOrigin: window.location.origin,
          workflowId,
          workflowName: workflow.data.name,
          variables: document.variables ?? [],
          secrets: availableSecrets.map(({ id, name }) => ({ id, name })),
        }),
        window.location.origin,
      );
      return data.session_id;
    },
    onSuccess: () => {
      setRecordingNote("Ready in the extension. Open the first page, then confirm from its popup.");
    },
  });

  const startRepick = useMutation({
    mutationFn: async (step: Step) => {
      if (connection.version === null || workflow.data === undefined) {
        throw new Error("The connected extension is not ready.");
      }
      const { data, error } = await createRecordingSession({
        path: { workflow_id: workflowId },
        headers: { "X-Extension-Version": connection.version },
        body: { mode: "repick", step_id: step.id },
      });
      if (error) throw error;
      window.postMessage(
        repickPendingMessage({
          sessionId: data.session_id,
          token: data.token,
          backendOrigin: window.location.origin,
          workflowId,
          workflowName: workflow.data.name,
          stepId: step.id,
        }),
        window.location.origin,
      );
      return {
        sessionId: data.session_id,
        token: data.token,
        stepId: step.id,
        old: targetsOf(step)[0]?.candidates ?? [],
        next: null,
      };
    },
    onSuccess: (session) => {
      setRepick(session);
      setRecordingNote(
        "Ready in the extension. Open the page that has the element, then confirm from its popup and click it.",
      );
    },
  });

  const confirmRepick = useMutation({
    mutationFn: async () => {
      if (repick === null || repick.next === null) {
        throw new Error("Nothing to confirm.");
      }
      const { error } = await finalizeRecordingSession({
        path: { session_id: repick.sessionId },
        headers: { authorization: repick.token },
        body: { candidates: repick.next },
      });
      if (error) throw error;
    },
    onSuccess: async () => {
      setRepick(null);
      setEdited(null);
      setRecordingNote("The Step's selectors were replaced.");
      await Promise.all([
        cache.invalidateQueries({ queryKey: draftKey(orgId, workflowId) }),
        cache.invalidateQueries({ queryKey: workflowKey(orgId, workflowId) }),
        cache.invalidateQueries({ queryKey: workflowsKey(orgId) }),
      ]);
    },
  });

  useEffect(() => {
    const receive = (event: MessageEvent) => {
      if (event.source !== window || event.origin !== window.location.origin) return;
      const message = readExtensionMessage(event.data);
      if (message?.type === REPICK_CANDIDATES && message.candidates !== undefined) {
        const candidates = message.candidates;
        setRepick((current) =>
          current !== null && current.sessionId === message.sessionId
            ? { ...current, next: candidates }
            : current,
        );
      }
      if (message?.type === RECORDING_FINISHED) {
        setRecordingNote("Recording saved to the Draft.");
        void Promise.all([
          cache.invalidateQueries({ queryKey: draftKey(orgId, workflowId) }),
          cache.invalidateQueries({ queryKey: workflowKey(orgId, workflowId) }),
          cache.invalidateQueries({ queryKey: workflowsKey(orgId) }),
          cache.invalidateQueries({ queryKey: SECRETS_KEY }),
        ]);
      }
      if (
        message?.type === RECORDING_TOKEN_EXPIRED &&
        message.sessionId !== undefined &&
        connection.version !== null
      ) {
        void createRecordingSession({
          path: { workflow_id: workflowId },
          headers: { "X-Extension-Version": connection.version },
          body: { session_id: message.sessionId },
        }).then(({ data, error }) => {
          if (error) {
            setRecordingNote(readRefusal(error));
            return;
          }
          window.postMessage(
            recordingTokenMessage(data.session_id, data.token),
            window.location.origin,
          );
          setRecordingNote("Recording resumed with every captured Step intact.");
        });
      }
    };
    window.addEventListener("message", receive);
    return () => {
      window.removeEventListener("message", receive);
    };
  }, [cache, connection.version, orgId, workflowId]);

  useEffect(() => {
    if (!unsaved) {
      return;
    }

    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!shouldAskBeforeLeave(true, here, null)) {
        return;
      }
      event.preventDefault();
      event.returnValue = "";
    };

    const onClick = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0) {
        return;
      }
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
        return;
      }
      const target = event.target;
      if (!(target instanceof Element)) {
        return;
      }
      const anchor = target.closest("a");
      if (anchor === null || anchor.target === "_blank" || anchor.hasAttribute("download")) {
        return;
      }
      const href = anchor.getAttribute("href");
      if (href === null || href === "" || href.startsWith("#")) {
        return;
      }
      let to: string;
      try {
        const url = new URL(href, window.location.origin);
        if (url.origin !== window.location.origin) {
          return;
        }
        to = `${url.pathname}${url.search}`;
      } catch {
        return;
      }
      if (!shouldAskBeforeLeave(true, here, to)) {
        return;
      }
      if (!window.confirm(LEAVE_PROMPT)) {
        event.preventDefault();
        event.stopPropagation();
      }
    };

    window.addEventListener("beforeunload", onBeforeUnload);
    window.document.addEventListener("click", onClick, true);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
      window.document.removeEventListener("click", onClick, true);
    };
  }, [here, unsaved]);

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
        cache.invalidateQueries({ queryKey: workflowKey(orgId, workflowId) }),
        cache.invalidateQueries({ queryKey: workflowsKey(orgId) }),
      ]);
    },
  });

  const restore = useMutation({
    mutationFn: async (number: number) => {
      const { error } = await restoreWorkflowVersion({
        path: { workflow_id: workflowId, number },
      });
      if (error) throw error;
    },
    onSuccess: async () => {
      setRestoring(null);
      setEdited(null);
      await Promise.all([
        cache.invalidateQueries({ queryKey: draftKey(orgId, workflowId) }),
        cache.invalidateQueries({ queryKey: workflowKey(orgId, workflowId) }),
        cache.invalidateQueries({ queryKey: workflowsKey(orgId) }),
      ]);
      router.push(versionPath(workflowId, null));
    },
  });

  const readOnly = viewing !== null;
  const document = readOnly ? (version.data ?? null) : (edited ?? draft.data ?? null);
  const steps = document?.steps ?? [];
  const workflowDefaultMs = workflow.data?.default_step_timeout_ms ?? 30_000;

  if (document === null) {
    const failed = readOnly ? version.error : draft.error;
    return failed ? <Callout tone="bad">{readRefusal(failed)}</Callout> : null;
  }

  const variables: Variable[] = document.variables ?? [];
  const secrets = secretNames(document);
  const usages = new Set(
    (
      variableRows(document).find((row) => row.name === highlighted) ??
      undeclaredRows(document).find((row) => row.name === highlighted)
    )?.usedBy ?? [],
  );

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

  const startRecording = () => {
    if (unsaved) {
      setRecordingNote("Save or discard your editor changes before recording.");
      return;
    }
    if (
      steps.length > 0 &&
      !window.confirm("Replace every Step in this Draft with a new recording?")
    ) {
      return;
    }
    recording.mutate(document);
  };

  const variablesButton = (
    <Button
      variant="secondary"
      onClick={() => {
        setDrawer(true);
      }}
    >
      <Braces className="size-3.5" />
      Variables
      <CountBadge count={variables.length} />
    </Button>
  );

  return (
    <>
      {save.error ? <Callout tone="bad">{saveRefusal(save.error)}</Callout> : null}
      {recording.error ? <Callout tone="bad">{readRefusal(recording.error)}</Callout> : null}
      {startRepick.error ? <Callout tone="bad">{readRefusal(startRepick.error)}</Callout> : null}
      {recordingNote ? <Callout tone="info">{recordingNote}</Callout> : null}

      {viewing === null ? null : (
        <Callout
          tone="info"
          size="banner"
          icon={<History className="size-4" />}
          title={`Reading v${String(viewing)}`}
          actions={
            <>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setRestoring(viewing);
                }}
              >
                Restore to Draft
              </Button>
              <Button
                variant="ghost"
                size="sm"
                nativeButton={false}
                render={<Link href={versionPath(workflowId, null)} />}
              >
                Back to the Draft
              </Button>
            </>
          }
        >
          A published Version never changes. Restore it to carry on from it in the Draft.
        </Callout>
      )}

      <div className="flex justify-end gap-2">
        {readOnly || connection.state !== "connected" || steps.length === 0 ? null : (
          <Button disabled={recording.isPending} onClick={startRecording}>
            Start recording
          </Button>
        )}
        {readOnly ? null : (
          <Button
            variant="secondary"
            onClick={() => {
              const blocked = testRunRefusal(
                workflow.data?.draft_state ?? "never-published",
                unsaved,
              );
              if (blocked !== null) {
                setRecordingNote(blocked);
                return;
              }
              setTesting(true);
            }}
          >
            <Play className="size-3.5" />
            Test run
          </Button>
        )}
        {variablesButton}
      </div>

      {highlighted === null ? null : (
        <Callout
          tone="secret"
          actions={
            <Button
              variant="ghost"
              size="sm"
              className="text-small"
              onClick={() => {
                setHighlighted(null);
              }}
            >
              Done
            </Button>
          }
        >
          {usages.size === 0
            ? `Nothing uses {{${highlighted}}} any more.`
            : `The steps that use {{${highlighted}}} are lit below.`}
        </Callout>
      )}

      <VariablesDrawer
        open={drawer}
        document={document}
        vault={(vault.data ?? []).map((secret) => ({ id: secret.id, name: secret.name }))}
        readOnly={readOnly}
        onOpenChange={setDrawer}
        onChange={setEdited}
        onShowUsages={setHighlighted}
      />

      {steps.length === 0 ? (
        <EmptyState
          absence={readOnly ? `v${String(viewing)} has no steps` : "Record your first steps"}
          whatFillsIt={
            readOnly
              ? "It was published from a Draft that had none."
              : "Record what you do in your own browser, or add a step here by hand."
          }
          action={
            readOnly ? undefined : (
              <div className="flex max-w-xl flex-col gap-3">
                {connection.state === "connected" ? (
                  <Button disabled={recording.isPending} onClick={startRecording}>
                    Start recording
                  </Button>
                ) : (
                  <InstallAndConnect compact />
                )}
                {addMenu}
              </div>
            )
          }
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
                  variables={variables}
                  secrets={secrets}
                  highlighted={usages.has(step.id)}
                  expanded={expanded === step.id}
                  readOnly={readOnly}
                  drifted={drift.data?.has(step.id) === true}
                  selectorOpen={repairing === step.id}
                  onExpand={(open) => {
                    setExpanded(open ? step.id : null);
                    if (!open && repairing === step.id) {
                      setRepairing(null);
                    }
                  }}
                  onChange={(next: Step) => {
                    setEdited(withStepReplaced(document, next));
                  }}
                  onConvert={(variable: Variable, span: Span) => {
                    setEdited(withLiteralMadeVariable(document, step.id, variable, span));
                  }}
                  onMove={(direction) => {
                    setEdited(withStepMoved(document, step.id, direction));
                  }}
                  onDelete={() => {
                    setEdited(withStepDeleted(document, step.id));
                  }}
                  onRepick={
                    readOnly || connection.state !== "connected"
                      ? undefined
                      : () => {
                          const blocked = repickRefusal(unsaved);
                          if (blocked !== null) {
                            setRecordingNote(blocked);
                            return;
                          }
                          startRepick.mutate(step);
                        }
                  }
                  onRepairDrift={() => {
                    const repair = repairFromDrift(step.id);
                    setExpanded(repair.expand);
                    setRepairing(repair.expand);
                  }}
                />
              ))}
            </ul>
          </Card>
          {readOnly ? null : <div className="flex justify-end">{addMenu}</div>}
        </>
      )}

      {unsaved && !readOnly ? (
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

      <TestRunDialog
        open={testing}
        workflowId={workflowId}
        fields={testRunFields(variables)}
        onOpenChange={setTesting}
      />

      <RepickDialog
        open={repick !== null && repick.next !== null}
        oldCandidates={repick?.old ?? []}
        newCandidates={repick?.next ?? []}
        pending={confirmRepick.isPending}
        refusal={confirmRepick.error ? readRefusal(confirmRepick.error) : null}
        onConfirm={() => {
          confirmRepick.mutate();
        }}
        onOpenChange={(open) => {
          if (!open) {
            setRepick(null);
          }
        }}
      />

      <RestoreDialog
        version={restoring}
        consequence={
          restoring === null
            ? ""
            : restoreConsequence(restoring, workflow.data?.draft_state ?? "never-published")
        }
        unsaved={unsaved}
        pending={restore.isPending}
        refusal={restore.error ? readRefusal(restore.error) : null}
        onConfirm={() => {
          if (restoring !== null) {
            restore.mutate(restoring);
          }
        }}
        onOpenChange={(open) => {
          if (!open) {
            setRestoring(null);
          }
        }}
      />
    </>
  );
}
