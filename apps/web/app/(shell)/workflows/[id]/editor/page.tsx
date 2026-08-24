"use client";

import {
  createRecordingSession,
  restoreWorkflowVersion,
  saveWorkflowDraft,
  type Variable,
  type WorkflowDocument,
} from "@step-by-step/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Braces, History, Plus } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { withStepAdded, withStepDeleted, withStepMoved, withStepReplaced } from "./edits";
import { readRefusal, saveRefusal } from "./messages";
import { draftKey, draftQuery, versionDocumentQuery } from "./queries";
import { RestoreDialog } from "./restore-dialog";
import { StepCard } from "./step-card";
import { ADDABLE_STEP_TYPES, STEP_TYPE_LABELS, blankStep, type Step } from "./steps";
import { VariablesDrawer } from "./variables-drawer";
import { secretNames, variableRows, withLiteralMadeVariable, type Span } from "./variables";

import { workflowKey, workflowQuery } from "../queries";
import { restoreConsequence, versionPath, viewedVersion } from "../versions";

import { workflowsKey } from "../../queries";

import { useActiveOrganization } from "../../../use-active-organization";

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
  readExtensionMessage,
  recordingPendingMessage,
  recordingTokenMessage,
} from "@/lib/extension-protocol";
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
 * Variables live in the same document and are edited from the drawer, so a
 * declaration, a rename, and the Steps that use it all travel in the one save
 * — which is also why a rename can rewrite every value that reaches for it.
 *
 * The same screen shows a published Version, when the address names one: the
 * card list again, over an immutable document, with everything that edits it
 * either gone or disabled and one way back into the Draft. A Version is the
 * same thing as a Draft with the changing stopped, so reading one is not a
 * second screen about it.
 *
 * Two things on this tab belong to later slices and are deliberately not
 * here: the selector panel behind a target's badge (`m6s5me`), and recording
 * and test runs (`7vuup5`, `2ggmhx`).
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
  const connection = useExtensionConnection();
  const cache = useQueryClient();
  const router = useRouter();
  const viewing = viewedVersion(useSearchParams().get("version"));
  const draft = useQuery(draftQuery(orgId, workflowId));
  const version = useQuery(versionDocumentQuery(orgId, workflowId, viewing));
  const workflow = useQuery(workflowQuery(orgId, workflowId));
  const [edited, setEdited] = useState<WorkflowDocument | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [drawer, setDrawer] = useState(false);
  const [highlighted, setHighlighted] = useState<string | null>(null);
  const [restoring, setRestoring] = useState<number | null>(null);
  const [recordingNote, setRecordingNote] = useState<string | null>(null);

  const recording = useMutation({
    mutationFn: async (document: WorkflowDocument) => {
      if (connection.version === null || workflow.data === undefined) {
        throw new Error("The connected extension is not ready.");
      }
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
        }),
        window.location.origin,
      );
      return data.session_id;
    },
    onSuccess: () => {
      setRecordingNote("Ready in the extension. Open the first page, then confirm from its popup.");
    },
  });

  useEffect(() => {
    const receive = (event: MessageEvent) => {
      if (event.source !== window || event.origin !== window.location.origin) return;
      const message = readExtensionMessage(event.data);
      if (message?.type === RECORDING_FINISHED) {
        setRecordingNote("Recording saved to the Draft.");
        void Promise.all([
          cache.invalidateQueries({ queryKey: draftKey(orgId, workflowId) }),
          cache.invalidateQueries({ queryKey: workflowKey(orgId, workflowId) }),
          cache.invalidateQueries({ queryKey: workflowsKey(orgId) }),
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

  /**
   * Restoring writes the Draft and leaves the Version alone, so what has to
   * be refetched afterwards is everything that reads the Draft: the document
   * itself, and the two places the chip is drawn from the comparison against
   * the latest Version. Then back to the Draft — restoring is done in order to
   * carry on editing.
   */
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
  // The edited copy wins while there is one, so a background refetch cannot
  // take somebody's unsaved work away from under them. It survives a look at a
  // Version too: reading one is not a reason to lose an hour of editing.
  const document = readOnly ? (version.data ?? null) : (edited ?? draft.data ?? null);
  const steps = document?.steps ?? [];
  const unsaved = edited !== null;
  const workflowDefaultMs = workflow.data?.default_step_timeout_ms ?? 30_000;

  if (document === null) {
    const failed = readOnly ? version.error : draft.error;
    return failed ? <Callout tone="bad">{readRefusal(failed)}</Callout> : null;
  }

  const variables: Variable[] = document.variables ?? [];
  const secrets = secretNames(document);
  // Which cards a drawer row lit up. The names are the document's, so a
  // highlight of a Variable that a later edit deletes simply lights nothing.
  const usages = new Set(
    variableRows(document).find((row) => row.name === highlighted)?.usedBy ?? [],
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
                  onExpand={(open) => {
                    setExpanded(open ? step.id : null);
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
