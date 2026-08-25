import type {
  ControlIntervalRecord,
  LogLine,
  RunControlKind,
  RunDetail,
  RunRecord,
  RunStatus,
  StepResultRecord,
} from "@step-by-step/api-client";

/**
 * How a live event advances the cockpit without a reload.
 *
 * Reconnection still refetches over REST — this reducer only applies events
 * that arrived after the last fetch, so it cannot disagree with Postgres for
 * long. Commands never travel on this path.
 */

export type CockpitSnapshot = {
  run: RunRecord;
  stepResults: StepResultRecord[];
  intervals: ControlIntervalRecord[];
  artifacts: RunDetail["artifacts"];
  logs: LogLine[];
  inFlight: { stepId: string; position: number; startedAt: string } | null;
};

export type RunEvent = {
  type: string;
  data: Record<string, unknown>;
};

export function emptySnapshot(run: RunRecord): CockpitSnapshot {
  return {
    run,
    stepResults: [],
    intervals: [],
    artifacts: [],
    logs: [],
    inFlight: null,
  };
}

export function snapshotFromDetail(detail: RunDetail, logs: LogLine[] = []): CockpitSnapshot {
  return {
    run: detail.run,
    stepResults: detail.step_results,
    intervals: detail.control_intervals,
    artifacts: detail.artifacts,
    logs,
    inFlight: null,
  };
}

export function applyRunEvent(state: CockpitSnapshot, event: RunEvent): CockpitSnapshot {
  if (event.type === "step.started") {
    return {
      ...state,
      inFlight: {
        stepId: stringOf(event.data.step_id),
        position: numberOf(event.data.position),
        startedAt: stringOf(event.data.at),
      },
    };
  }
  if (event.type === "step.finished") {
    return finishStep(state, event.data);
  }
  if (event.type === "run.status") {
    return {
      ...state,
      inFlight: null,
      run: {
        ...state.run,
        status: event.data.status as RunStatus,
        failure_reason:
          typeof event.data.failure_reason === "string"
            ? (event.data.failure_reason as RunRecord["failure_reason"])
            : state.run.failure_reason,
        failure_detail:
          typeof event.data.failure_detail === "string"
            ? event.data.failure_detail
            : state.run.failure_detail,
        ended_at: stringOf(event.data.at),
      },
    };
  }
  if (event.type === "control") {
    return shiftControl(state, event.data);
  }
  if (event.type === "log") {
    return appendLog(state, event.data);
  }
  return state;
}

function finishStep(state: CockpitSnapshot, data: Record<string, unknown>): CockpitSnapshot {
  const stepId = stringOf(data.step_id);
  const startedAt =
    state.inFlight?.stepId === stepId ? state.inFlight.startedAt : stringOf(data.at);
  const extracted =
    typeof data.extracted_count === "number"
      ? Array.from({ length: data.extracted_count }, () => ({}))
      : null;
  const next: StepResultRecord = {
    id: `live-${stepId}`,
    step_id: stepId,
    position: state.inFlight?.stepId === stepId ? state.inFlight.position : 0,
    status: data.status as StepResultRecord["status"],
    started_at: startedAt,
    ended_at: stringOf(data.at),
    matched_candidate_rank: numberOrNull(data.matched_candidate_rank),
    candidate_count: numberOrNull(data.candidate_count),
    completed_by_human: data.completed_by_human === true,
    error_code: typeof data.error_code === "string" ? data.error_code : null,
    error_message: typeof data.error_message === "string" ? data.error_message : null,
    diagnostics: null,
    extracted_value: extracted,
  };
  const without = state.stepResults.filter((result) => result.step_id !== stepId);
  return {
    ...state,
    inFlight: state.inFlight?.stepId === stepId ? null : state.inFlight,
    stepResults: [...without, next].sort((a, b) => a.position - b.position),
  };
}

function shiftControl(state: CockpitSnapshot, data: Record<string, unknown>): CockpitSnapshot {
  const at = stringOf(data.at);
  const phase = data.phase as RunControlKind;
  const closed = state.intervals.map((interval, index) =>
    index === state.intervals.length - 1 && interval.ended_at === null
      ? { ...interval, ended_at: at }
      : interval,
  );
  return {
    ...state,
    intervals: [
      ...closed,
      {
        id: `live-${phase}-${at}`,
        kind: phase,
        started_at: at,
        ended_at: null,
      },
    ],
  };
}

function appendLog(state: CockpitSnapshot, data: Record<string, unknown>): CockpitSnapshot {
  const seq = numberOf(data.seq);
  if (state.logs.some((line) => line.seq === seq)) {
    return state;
  }
  const line: LogLine = {
    seq,
    step_id: typeof data.step_id === "string" ? data.step_id : null,
    level: (typeof data.level === "string" ? data.level : "info") as LogLine["level"],
    text: stringOf(data.text),
    at: stringOf(data.at),
  };
  return { ...state, logs: [...state.logs, line] };
}

function stringOf(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function numberOf(value: unknown): number {
  return typeof value === "number" ? value : 0;
}

function numberOrNull(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}
