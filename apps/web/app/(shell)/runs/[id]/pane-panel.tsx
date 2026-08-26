"use client";

import {
  abandonTakeover,
  consentRunAuthState,
  handBackRun,
  holdTakeover,
  pauseRun,
  takeOverRun,
  type AuthStateConsentScope,
  type RunTrigger,
} from "@step-by-step/api-client";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import type { DiagnosticEvent, PredicateState } from "./events";
import { refusalMessage } from "./messages";
import {
  challengeBanner,
  consentPrompts,
  countdownState,
  paneView,
  predicateLine,
  waitingReason,
} from "./pane";
import { VncScreen } from "./vnc-screen";

import type { Step } from "../../workflows/[id]/editor/steps";

import { Callout } from "@/components/primitives/callout";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * The cockpit's main pane: the Worker's browser, the waiting card, the
 * control bar, the unmet choice, the challenge banner, and consent.
 */

export function PanePanel({
  runId,
  status,
  cancelling,
  phase,
  workerId,
  trigger,
  deadlineAt,
  pauseRequested,
  autoHandbackDisabled,
  pause,
  predicate,
  diagnostics,
  candidates,
  weHoldControl,
  heldElsewhere,
  unmetHandback,
  now,
  onTookOver,
  onReleased,
  onUnmet,
  onStay,
  onPause,
  onConsented,
  onCancel,
  onError,
}: {
  runId: string;
  status: Parameters<typeof paneView>[0]["status"];
  cancelling: boolean;
  phase: Parameters<typeof paneView>[0]["phase"];
  workerId: string | null;
  trigger: RunTrigger;
  deadlineAt: string | null;
  pauseRequested: boolean;
  autoHandbackDisabled: boolean;
  pause: Extract<Step, { type: "pause-for-takeover" }> | null;
  predicate: PredicateState | null;
  diagnostics: DiagnosticEvent[];
  candidates: Parameters<typeof consentPrompts>[0];
  weHoldControl: boolean;
  heldElsewhere: boolean;
  unmetHandback: boolean;
  now: Date;
  onTookOver: () => void;
  onReleased: () => void;
  onUnmet: () => void;
  onStay: () => void;
  onPause: () => void;
  onConsented: (domain: string, scope: AuthStateConsentScope) => void;
  onCancel: () => void;
  onError: (error: unknown) => void;
}) {
  const view = paneView({
    status,
    cancelling,
    phase,
    weHoldControl,
    heldElsewhere,
    unmetHandback,
    workerId,
  });
  const tick = countdownState(deadlineAt, now);
  const check = predicateLine({
    hasCheck: pause?.payload.successCheck != null,
    met: predicate?.met ?? null,
    graceEndsAt: predicate?.graceEndsAt ?? null,
    autoHandbackDisabled,
    now,
    controlling: view.showControlBar,
  });
  const prompts = consentPrompts(candidates, trigger);
  const [dismissed, setDismissed] = useState<ReadonlySet<string>>(new Set());
  const banners = diagnostics
    .filter((item) => !dismissed.has(`${item.stepId}:${item.kind}`))
    .map((item) => ({ item, copy: challengeBanner(item) }))
    .filter((entry) => entry.copy !== null);

  const takeOver = useMutation({
    mutationFn: async () => {
      const { error } = await takeOverRun({ path: { run_id: runId } });
      if (error) throw error;
    },
    onSuccess: onTookOver,
    onError,
  });
  const handBack = useMutation({
    mutationFn: async () => {
      const { error } = await handBackRun({ path: { run_id: runId } });
      if (error) throw error;
    },
    onSuccess: onReleased,
    onError,
  });
  const stay = useMutation({
    mutationFn: async () => {
      const { error } = await holdTakeover({
        path: { run_id: runId },
        body: { auto_handback: false },
      });
      if (error) throw error;
    },
    onSuccess: onStay,
    onError,
  });
  const giveUp = useMutation({
    mutationFn: async () => {
      const { error } = await abandonTakeover({ path: { run_id: runId } });
      if (error) throw error;
    },
    onSuccess: onReleased,
    onError,
  });
  const requestPause = useMutation({
    mutationFn: async () => {
      const { error } = await pauseRun({ path: { run_id: runId } });
      if (error) throw error;
    },
    onSuccess: onPause,
    onError,
  });
  const consent = useMutation({
    mutationFn: async (asked: { domain: string; scope: AuthStateConsentScope }) => {
      const { error } = await consentRunAuthState({
        path: { run_id: runId },
        body: asked,
      });
      if (error) throw error;
      return asked;
    },
    onSuccess: (asked) => {
      onConsented(asked.domain, asked.scope);
    },
    onError,
  });

  const showChallenge = status === "running" && !cancelling;
  const live = view.frame === "view_only" || view.frame === "interactive";

  return (
    <div className="flex flex-col gap-3">
      {showChallenge
        ? banners.map(({ item, copy }) =>
            copy === null ? null : (
              <Callout
                key={`${item.stepId}:${item.at}`}
                tone="warn"
                size="banner"
                title={copy.title}
                actions={
                  <>
                    <Button
                      size="sm"
                      disabled={requestPause.isPending}
                      onClick={() => {
                        requestPause.mutate();
                      }}
                    >
                      {copy.action}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setDismissed((current) =>
                          new Set(current).add(`${item.stepId}:${item.kind}`),
                        );
                      }}
                    >
                      Dismiss
                    </Button>
                  </>
                }
              />
            ),
          )
        : null}

      {prompts.map((prompt) => (
        <Callout
          key={prompt.domain}
          tone="secret"
          size="banner"
          title={prompt.question}
          actions={
            <>
              {prompt.scopes.map((scope) => (
                <Button
                  key={scope}
                  size="sm"
                  disabled={consent.isPending}
                  onClick={() => {
                    consent.mutate({ domain: prompt.domain, scope });
                  }}
                >
                  {scope === "personal" ? "Keep just for me" : "Keep for the organization"}
                </Button>
              ))}
            </>
          }
        />
      ))}

      {view.showWaitingCard ? (
        <WaitingCard
          reason={waitingReason(pause, pauseRequested)}
          tick={tick}
          check={check}
          busy={takeOver.isPending}
          onTakeOver={() => {
            takeOver.mutate();
          }}
          onCancel={onCancel}
        />
      ) : null}

      {view.showUnmetChoice ? (
        <Callout
          tone="warn"
          size="banner"
          title="Success check not met."
          actions={
            <>
              <Button
                size="sm"
                disabled={takeOver.isPending}
                onClick={() => {
                  onUnmet();
                  takeOver.mutate();
                }}
              >
                {view.unmetKeep}
              </Button>
              <Button
                size="sm"
                variant="destructive"
                disabled={giveUp.isPending}
                onClick={() => {
                  giveUp.mutate();
                }}
              >
                {view.unmetGiveUp}
              </Button>
            </>
          }
        >
          Automation has not resumed; the browser is still being held
          {tick === null ? "." : ` (${tick.label}).`}
        </Callout>
      ) : null}

      {view.showHeldNote && view.heldNote !== null ? (
        <Callout tone="secret" size="banner">
          {view.heldNote}
        </Callout>
      ) : null}

      {view.showControlBar ? (
        <ControlBar
          identity={view.identity ?? "You are controlling this browser"}
          tick={tick}
          busy={handBack.isPending}
          onHandBack={() => {
            handBack.mutate();
          }}
          onCancel={onCancel}
        />
      ) : null}

      <div
        className={cn(
          "relative overflow-hidden rounded-md border",
          view.highlight === "wait" && "border-wait",
          view.highlight === "human" && "border-human",
          view.highlight === "none" && "border-line",
        )}
      >
        {live ? (
          <VncScreen runId={runId} interactive={view.frame === "interactive"} enabled={live} />
        ) : (
          <div className="flex min-h-48 items-center justify-center bg-muted text-half text-mut">
            {view.caption}
          </div>
        )}
        {live && view.caption !== null ? (
          <span className="pointer-events-none absolute top-2 left-2 rounded-md bg-panel/90 px-2 py-1 text-micro text-mut">
            {view.caption}
          </span>
        ) : null}
      </div>

      {view.showControlBar || view.showWaitingCard ? (
        <PredicateLine check={check} stay={stay} handBack={handBack} />
      ) : null}

      {takeOver.error ? <Callout tone="bad">{refusalMessage(takeOver.error)}</Callout> : null}
    </div>
  );
}

function WaitingCard({
  reason,
  tick,
  check,
  busy,
  onTakeOver,
  onCancel,
}: {
  reason: string;
  tick: ReturnType<typeof countdownState>;
  check: ReturnType<typeof predicateLine>;
  busy: boolean;
  onTakeOver: () => void;
  onCancel: () => void;
}) {
  return (
    <Callout
      tone="warn"
      size="banner"
      title="This run is waiting for you"
      actions={
        <>
          <Button size="sm" disabled={busy} onClick={onTakeOver}>
            take over browser
          </Button>
          <Button size="sm" variant="destructive" onClick={onCancel}>
            cancel run
          </Button>
        </>
      }
    >
      <p>{reason}</p>
      {tick === null ? null : (
        <p className={cn("font-semibold", tick.low && "text-bad")}>
          {tick.label} before the run fails
        </p>
      )}
      {check.state === "none" ? null : (
        <p>Success check: currently {check.state === "met" ? "met" : "unmet"}</p>
      )}
    </Callout>
  );
}

function ControlBar({
  identity,
  tick,
  busy,
  onHandBack,
  onCancel,
}: {
  identity: string;
  tick: ReturnType<typeof countdownState>;
  busy: boolean;
  onHandBack: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md bg-human px-3 py-2 text-small text-panel">
      <span className="font-semibold">{identity}</span>
      <span className="ml-auto" />
      {tick === null ? null : (
        <span className={cn("font-semibold", tick.low && "text-bad")}>{tick.label}</span>
      )}
      <Button size="sm" variant="secondary" disabled={busy} onClick={onHandBack}>
        hand control back
      </Button>
      <Button size="sm" variant="destructive" onClick={onCancel}>
        cancel run
      </Button>
    </div>
  );
}

function PredicateLine({
  check,
  stay,
  handBack,
}: {
  check: ReturnType<typeof predicateLine>;
  stay: { isPending: boolean; mutate: () => void };
  handBack: { isPending: boolean; mutate: () => void };
}) {
  if (check.state === "none") {
    return null;
  }
  return (
    <div className="flex flex-wrap items-center gap-2 text-half">
      <span>
        Success check: currently{" "}
        <span
          className={check.state === "met" ? "font-semibold text-ok" : "font-semibold text-wait"}
        >
          {check.state}
        </span>
      </span>
      {check.grace === null ? null : <span className="text-ok">{check.grace}</span>}
      {check.offerHandBackNow ? (
        <Button
          size="sm"
          disabled={handBack.isPending}
          onClick={() => {
            handBack.mutate();
          }}
        >
          hand back now
        </Button>
      ) : null}
      {check.offerStay ? (
        <Button
          size="sm"
          variant="outline"
          disabled={stay.isPending}
          onClick={() => {
            stay.mutate();
          }}
        >
          stay in control
        </Button>
      ) : null}
    </div>
  );
}
