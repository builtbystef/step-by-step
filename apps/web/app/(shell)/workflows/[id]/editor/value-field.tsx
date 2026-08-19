"use client";

import type { Variable } from "@step-by-step/api-client";
import { Braces, KeyRound } from "lucide-react";
import { useRef, useState } from "react";

import { declarationRefusal, withReferenceInserted, type Span } from "./variables";

import { Callout } from "@/components/primitives/callout";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";

/**
 * A value that interpolates Variables: a navigate URL, or what a type Step
 * types.
 *
 * The field itself is a text box holding text, because that is what the value
 * is — literal text and `{{name}}` mixed freely, and the card's sentence is
 * where they are drawn as pills. What the field adds is the two ways a
 * Variable gets into it: a dropdown that writes `{{name}}` at the caret, and
 * making one out of what is already there.
 *
 * That second one is how a recording becomes reusable. The recorder writes
 * the account name a person typed as a literal; converting it declares the
 * Variable and leaves a reference in its place, in one edit, so the document
 * is never in the state the store refuses.
 */
export function ValueField({
  label,
  hint,
  placeholder,
  value,
  variables,
  onChange,
  onConvert,
}: {
  label: string;
  hint: string;
  placeholder?: string;
  value: string;
  variables: Variable[];
  onChange: (value: string) => void;
  onConvert: (variable: Variable, span: Span) => void;
}) {
  // Where the caret was when the field last had it. A menu item takes the
  // focus away before it is clicked, so the field cannot be asked afterwards.
  const caret = useRef<Span>({ from: value.length, to: value.length });
  const [converting, setConverting] = useState(false);

  const selected = (): Span =>
    caret.current.from < caret.current.to && caret.current.to <= value.length
      ? caret.current
      : { from: 0, to: value.length };

  return (
    <div className="flex flex-col gap-1">
      <span className="text-small font-semibold text-ink">{label}</span>
      <div className="flex items-center gap-2">
        <Input
          aria-label={label}
          value={value}
          placeholder={placeholder}
          onChange={(typed) => {
            caret.current = {
              from: typed.target.selectionStart ?? typed.target.value.length,
              to: typed.target.selectionEnd ?? typed.target.value.length,
            };
            onChange(typed.target.value);
          }}
          onSelect={(moved) => {
            const field = moved.currentTarget;
            caret.current = {
              from: field.selectionStart ?? value.length,
              to: field.selectionEnd ?? value.length,
            };
          }}
        />
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button variant="secondary" size="sm" className="text-small">
                <Braces className="size-3.5" />
                Variable
              </Button>
            }
          />
          <DropdownMenuContent align="end">
            {variables.length === 0 ? (
              <DropdownMenuItem disabled>Nothing declared yet</DropdownMenuItem>
            ) : (
              variables.map((variable) => (
                <DropdownMenuItem
                  key={variable.name}
                  onClick={() => {
                    onChange(withReferenceInserted(value, variable.name, caret.current.from));
                  }}
                >
                  {variable.secret === true ? <KeyRound className="size-3.5 text-human" /> : null}
                  <span className="font-mono text-small">{`{{${variable.name}}}`}</span>
                </DropdownMenuItem>
              ))
            )}
            <DropdownMenuItem
              disabled={value === ""}
              onClick={() => {
                setConverting(true);
              }}
            >
              Make a Variable of this value…
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <span className="text-small text-mut">{hint}</span>

      {converting ? (
        <ConvertForm
          literal={value.slice(selected().from, selected().to)}
          variables={variables}
          onCancel={() => {
            setConverting(false);
          }}
          onConvert={(variable) => {
            onConvert(variable, selected());
            setConverting(false);
          }}
        />
      ) : null}
    </div>
  );
}

/** Naming the Variable a literal becomes, and saying whether it is secret. */
function ConvertForm({
  literal,
  variables,
  onCancel,
  onConvert,
}: {
  literal: string;
  variables: Variable[];
  onCancel: () => void;
  onConvert: (variable: Variable) => void;
}) {
  const [name, setName] = useState("");
  const [secret, setSecret] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);

  return (
    <form
      className="mt-1 flex flex-col gap-2 rounded-md border border-human/30 bg-human-bg/40 p-3"
      onSubmit={(submitted) => {
        submitted.preventDefault();
        const refused = declarationRefusal({ variables }, name);
        setRefusal(refused);
        if (refused === null) {
          onConvert({ name, secret });
        }
      }}
    >
      <p className="text-half text-ink">
        <span className="rounded bg-muted px-1 font-mono text-small">{literal}</span> becomes a
        Variable, and the value keeps a reference to it.
      </p>
      <div className="flex items-center gap-2">
        <Input
          aria-label="Name of the new Variable"
          className="font-mono text-small"
          placeholder="tenant"
          autoComplete="off"
          autoFocus
          value={name}
          onChange={(typed) => {
            setName(typed.target.value);
          }}
        />
        <Button type="submit" variant="secondary" size="sm" className="text-small">
          Make it a Variable
        </Button>
        <Button variant="ghost" size="sm" className="text-small" onClick={onCancel}>
          Cancel
        </Button>
      </div>
      <label className="flex items-center gap-2 text-half text-ink">
        <input
          type="checkbox"
          className="size-4 accent-human"
          checked={secret}
          onChange={(ticked) => {
            setSecret(ticked.target.checked);
          }}
        />
        Secret — supplied per Run, never stored in a Step
      </label>
      {refusal === null ? null : <Callout tone="warn">{refusal}</Callout>}
    </form>
  );
}
