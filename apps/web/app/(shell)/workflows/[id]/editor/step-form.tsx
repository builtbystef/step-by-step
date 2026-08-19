"use client";

import type { ExtractField, Target, Variable } from "@step-by-step/api-client";
import type { ReactNode } from "react";

import { targetHealth } from "./badges";
import type { Step } from "./steps";
import { targetToken } from "./summary";
import { ValueField } from "./value-field";
import type { Span } from "./variables";

import { Callout } from "@/components/primitives/callout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { duration } from "@/lib/duration";
import { cn } from "@/lib/utils";

/**
 * A card, expanded: everything this Step holds, editable in place.
 *
 * Two halves. The payload is what this type of Step does, and it is the only
 * part that differs between the eight. The envelope is what every Step
 * carries whatever it does — optional, off, a timeout of its own, and whether
 * to keep a screenshot — and it reads the same on all eight, so that a person
 * learns it once.
 *
 * What is shown but not edited here is the target's candidate list. It is
 * plain stored data and it is repairable, but both repair paths — re-picking
 * the element on the live page and hand-editing the candidates — are the
 * selector panel's, which arrives with `m6s5me`. Until then this form says
 * what a Step finds its element by, and never pretends the list is empty.
 *
 * The whole form is one `fieldset`, which is how a published Version opens
 * read-only: a disabled fieldset disables every control inside it, so a
 * Version cannot be edited by a control a later slice forgot to thread a flag
 * through. Immutability is the platform's here, not a prop's.
 */
export function StepForm({
  step,
  workflowDefaultMs,
  variables,
  readOnly,
  onChange,
  onConvert,
}: {
  step: Step;
  workflowDefaultMs: number;
  variables: Variable[];
  readOnly: boolean;
  onChange: (step: Step) => void;
  onConvert: (variable: Variable, span: Span) => void;
}) {
  return (
    <fieldset
      disabled={readOnly}
      className="mt-3 flex min-w-0 flex-col gap-4 rounded-md border border-line bg-bg/60 p-3"
    >
      <Payload step={step} variables={variables} onChange={onChange} onConvert={onConvert} />
      <Envelope step={step} workflowDefaultMs={workflowDefaultMs} onChange={onChange} />
    </fieldset>
  );
}

/** What this Step does — the half of the form that differs between the eight. */
function Payload({
  step,
  variables,
  onChange,
  onConvert,
}: {
  step: Step;
  variables: Variable[];
  onChange: (step: Step) => void;
  onConvert: (variable: Variable, span: Span) => void;
}) {
  switch (step.type) {
    case "navigate":
      return (
        <ValueField
          label="URL"
          hint="Literal text and Variables mix freely — {{name}} is filled in per Run."
          placeholder="https://example.com/invoices"
          value={step.payload.url}
          variables={variables}
          onChange={(url) => {
            onChange({ ...step, payload: { ...step.payload, url } });
          }}
          onConvert={onConvert}
        />
      );
    case "click":
      return (
        <>
          <TargetField target={step.payload.target} step={step} />
          <Check
            label="Expect this click to load a new page"
            checked={step.payload.assertedNavigation === true}
            onChange={(asserted) => {
              onChange({ ...step, payload: { ...step.payload, assertedNavigation: asserted } });
            }}
          />
        </>
      );
    case "type":
      return (
        <>
          <TargetField target={step.payload.target} step={step} />
          <ValueField
            label="Value"
            hint="A secret Variable never lands here — {{name}} is all the Step keeps."
            value={step.payload.value}
            variables={variables}
            onChange={(value) => {
              onChange({ ...step, payload: { ...step.payload, value } });
            }}
            onConvert={onConvert}
          />
        </>
      );
    case "select":
      return (
        <>
          <TargetField target={step.payload.target} step={step} />
          <Field label="Option" hint="The option to choose, as the list writes it.">
            <Input
              value={step.payload.value}
              onChange={(typed) => {
                onChange({ ...step, payload: { ...step.payload, value: typed.target.value } });
              }}
            />
          </Field>
        </>
      );
    case "download":
      return <TargetField target={step.payload.target} step={step} />;
    case "extract":
      return <ExtractPayload step={step} onChange={onChange} />;
    case "wait":
      return <WaitPayload step={step} onChange={onChange} />;
    case "pause-for-takeover":
      return <TakeoverPayload step={step} onChange={onChange} />;
  }
}

/** An extraction: one named value, or a flat list of records. */
function ExtractPayload({
  step,
  onChange,
}: {
  step: Extract<Step, { type: "extract" }>;
  onChange: (step: Step) => void;
}) {
  const payload = step.payload;
  return (
    <>
      <TargetField target={payload.target} step={step} />
      <Field label="Save it as" hint="The name a Run reports this value under.">
        <Input
          value={payload.outputName}
          onChange={(typed) => {
            onChange({ ...step, payload: { ...payload, outputName: typed.target.value } });
          }}
        />
      </Field>
      <Field label="What to take" hint="One value, or one record per repeating element.">
        <Choice
          value={payload.mode}
          options={[
            { value: "scalar", label: "One value" },
            { value: "list", label: "A list of records" },
          ]}
          onChange={(mode) => {
            onChange(
              mode === "scalar"
                ? {
                    ...step,
                    payload: {
                      target: payload.target,
                      outputName: payload.outputName,
                      mode: "scalar",
                    },
                  }
                : {
                    ...step,
                    payload: {
                      target: payload.target,
                      outputName: payload.outputName,
                      mode: "list",
                      fields: [{ name: "", subSelector: "" }],
                    },
                  },
            );
          }}
        />
      </Field>
      {payload.mode === "scalar" ? (
        <Field label="Attribute" hint="Left empty, the element's text is taken.">
          <Input
            value={payload.attribute ?? ""}
            placeholder="href"
            onChange={(typed) => {
              onChange({
                ...step,
                payload: { ...payload, attribute: blankToNull(typed.target.value) },
              });
            }}
          />
        </Field>
      ) : (
        <Group label="Fields" hint="One column each, found inside the repeating element.">
          <div className="flex flex-col gap-2">
            {payload.fields.map((field, at) => (
              <div key={at} className="flex items-center gap-2">
                <Input
                  aria-label={`Field ${String(at + 1)} name`}
                  placeholder="price"
                  value={field.name}
                  onChange={(typed) => {
                    onChange({
                      ...step,
                      payload: {
                        ...payload,
                        fields: replacedAt(payload.fields, at, {
                          ...field,
                          name: typed.target.value,
                        }),
                      },
                    });
                  }}
                />
                <Input
                  aria-label={`Field ${String(at + 1)} sub-selector`}
                  placeholder=".price"
                  className="font-mono text-small"
                  value={field.subSelector}
                  onChange={(typed) => {
                    onChange({
                      ...step,
                      payload: {
                        ...payload,
                        fields: replacedAt(payload.fields, at, {
                          ...field,
                          subSelector: typed.target.value,
                        }),
                      },
                    });
                  }}
                />
                <Input
                  aria-label={`Field ${String(at + 1)} attribute`}
                  placeholder="text"
                  value={field.attribute ?? ""}
                  onChange={(typed) => {
                    onChange({
                      ...step,
                      payload: {
                        ...payload,
                        fields: replacedAt(payload.fields, at, {
                          ...field,
                          attribute: blankToNull(typed.target.value),
                        }),
                      },
                    });
                  }}
                />
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-small"
                  disabled={payload.fields.length === 1}
                  title={
                    payload.fields.length === 1 ? "A list extraction needs a field." : undefined
                  }
                  onClick={() => {
                    onChange({
                      ...step,
                      payload: {
                        ...payload,
                        fields: payload.fields.filter((_, which) => which !== at),
                      },
                    });
                  }}
                >
                  Remove
                </Button>
              </div>
            ))}
            <Button
              variant="secondary"
              size="sm"
              className="self-start text-small"
              onClick={() => {
                onChange({
                  ...step,
                  payload: {
                    ...payload,
                    fields: [...payload.fields, { name: "", subSelector: "" }],
                  },
                });
              }}
            >
              Add field
            </Button>
          </div>
        </Group>
      )}
    </>
  );
}

/**
 * A wait: a fixed length of time, or an element to wait for.
 *
 * Which of the two it is was decided when the Step was made, and it stays
 * decided: turning a duration into an element wait would need a candidate
 * list, which only a recording or a Re-pick can produce.
 */
function WaitPayload({
  step,
  onChange,
}: {
  step: Extract<Step, { type: "wait" }>;
  onChange: (step: Step) => void;
}) {
  const payload = step.payload;
  if (payload.mode === "element") {
    return <TargetField target={payload.target} step={step} label="Wait for this element" />;
  }
  return (
    <Field label="Wait for" hint="A pause of a fixed length, before the next Step.">
      <Milliseconds
        value={payload.durationMs}
        onChange={(ms) => {
          onChange({ ...step, payload: { ...payload, durationMs: ms ?? 1 } });
        }}
      />
    </Field>
  );
}

/** A pause: what the person is asked, how long it waits, and how it ends. */
function TakeoverPayload({
  step,
  onChange,
}: {
  step: Extract<Step, { type: "pause-for-takeover" }>;
  onChange: (step: Step) => void;
}) {
  const payload = step.payload;
  return (
    <>
      <Field label="Message" hint="What the person taking over is asked to do.">
        <Input
          value={payload.message ?? ""}
          placeholder="Solve the captcha, then hand control back."
          onChange={(typed) => {
            onChange({
              ...step,
              payload: { ...payload, message: blankToNull(typed.target.value) },
            });
          }}
        />
      </Field>
      <Field label="Give up after" hint="Left empty, the Workflow's takeover timeout applies.">
        <Milliseconds
          value={payload.timeoutMs ?? null}
          onChange={(ms) => {
            onChange({ ...step, payload: { ...payload, timeoutMs: ms } });
          }}
        />
      </Field>
      <Group
        label="Done when this appears"
        hint="The element whose appearance means the person has finished. Without one, the hand-back stays manual."
      >
        {payload.successCheck ? (
          <div className="flex items-center gap-2">
            <TargetSummary target={payload.successCheck} />
            <Button
              variant="ghost"
              size="sm"
              className="text-small"
              onClick={() => {
                onChange({ ...step, payload: { ...payload, successCheck: null } });
              }}
            >
              Remove
            </Button>
          </div>
        ) : (
          <p className="text-half text-mut">Nothing — this pause ends when the person says so.</p>
        )}
      </Group>
    </>
  );
}

/** The envelope: what every Step carries, whatever type it is. */
function Envelope({
  step,
  workflowDefaultMs,
  onChange,
}: {
  step: Step;
  workflowDefaultMs: number;
  onChange: (step: Step) => void;
}) {
  return (
    <div className="flex flex-col gap-3 border-t border-line pt-3">
      <Field
        label="Timeout"
        hint={`Left empty, this Step waits the workflow default of ${duration(workflowDefaultMs)}.`}
      >
        <Milliseconds
          value={step.timeoutMs ?? null}
          placeholder={duration(workflowDefaultMs)}
          onChange={(ms) => {
            onChange({ ...step, timeoutMs: ms });
          }}
        />
      </Field>
      <div className="flex flex-wrap gap-4">
        <Check
          label="Optional — skip it rather than fail the Run"
          checked={step.optional === true}
          onChange={(optional) => {
            onChange({ ...step, optional });
          }}
        />
        <Check
          label="Off — keep it here, do not run it"
          checked={step.disabled === true}
          onChange={(disabled) => {
            onChange({ ...step, disabled });
          }}
        />
      </div>
    </div>
  );
}

/** What this Step finds its element by, and how well that is expected to go. */
function TargetField({
  target,
  step,
  label = "Element",
}: {
  target: Target;
  step: Step;
  label?: string;
}) {
  const health = targetHealth(step);
  return (
    <Group
      label={label}
      hint="Repairing how a Step finds its element arrives with the selector panel."
    >
      <div className="flex flex-col gap-2">
        <TargetSummary target={target} />
        {health.state === "unsupported" ? (
          <Callout tone="bad">{health.warning}</Callout>
        ) : health.state === "fragile" ? (
          <Callout tone="warn">
            Only where this element sat on the page was recorded, so a layout change will lose it.
          </Callout>
        ) : null}
      </div>
    </Group>
  );
}

/** One line about a target: what it is called, and how many ways there are to it. */
function TargetSummary({ target }: { target: Target }) {
  const token = targetToken(target);
  const ways = target.candidates.length;
  return (
    <p className="text-half text-ink">
      <span className={cn("rounded bg-muted px-1", token.machine && "font-mono text-small")}>
        {token.text}
      </span>
      <span className="ml-2 text-small text-mut">
        {ways === 0
          ? "no recorded way of finding it"
          : `${String(ways)} way${ways === 1 ? "" : "s"} to find it, verified when recorded`}
      </span>
    </p>
  );
}

/**
 * One thing to fill in: its name, the control, and the sentence under it.
 *
 * A `<label>` when there is one control to name, and a plain group when there
 * are several — a label wrapping a row of inputs and a button would hand
 * every click on that row to the first input.
 */
function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-small font-semibold text-ink">{label}</span>
      {children}
      {hint === undefined ? null : <span className="text-small text-mut">{hint}</span>}
    </label>
  );
}

function Group({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-small font-semibold text-ink">{label}</span>
      {children}
      {hint === undefined ? null : <span className="text-small text-mut">{hint}</span>}
    </div>
  );
}

function Check({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-half text-ink">
      <input
        type="checkbox"
        className="size-4 accent-accent"
        checked={checked}
        onChange={(ticked) => {
          onChange(ticked.target.checked);
        }}
      />
      {label}
    </label>
  );
}

function Choice<Value extends string>({
  value,
  options,
  onChange,
}: {
  value: Value;
  options: { value: Value; label: string }[];
  onChange: (value: Value) => void;
}) {
  return (
    <select
      className="h-9 w-fit rounded-md border border-line bg-panel px-2 text-half text-ink"
      value={value}
      onChange={(chosen) => {
        onChange(chosen.target.value as Value);
      }}
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

/**
 * A length of time, typed in seconds and stored in milliseconds — the unit
 * the document keeps and the unit a person thinks in are not the same one.
 */
function Milliseconds({
  value,
  placeholder,
  onChange,
}: {
  value: number | null;
  placeholder?: string;
  onChange: (ms: number | null) => void;
}) {
  return (
    <span className="flex items-center gap-2">
      <Input
        type="number"
        min={0}
        step="0.1"
        className="w-32"
        value={value === null ? "" : String(value / 1000)}
        placeholder={placeholder}
        onChange={(typed) => {
          const seconds = Number(typed.target.value);
          onChange(
            typed.target.value === "" || Number.isNaN(seconds) || seconds <= 0
              ? null
              : Math.round(seconds * 1000),
          );
        }}
      />
      <span className="text-small text-mut">seconds</span>
    </span>
  );
}

/** An empty field means absent, which is what every optional value here means. */
function blankToNull(typed: string): string | null {
  return typed === "" ? null : typed;
}

function replacedAt(fields: ExtractField[], at: number, field: ExtractField): ExtractField[] {
  return fields.map((existing, which) => (which === at ? field : existing));
}
