"use client";

import type { Variable, WorkflowDocument } from "@step-by-step/api-client";
import { KeyRound, Trash2 } from "lucide-react";
import { useState } from "react";

import {
  declarationRefusal,
  deletionRefusal,
  variableRows,
  withVariableDeclared,
  withVariableDeleted,
  withVariableRenamed,
  withVariableSecret,
  type VariableRow,
} from "./variables";

import { AttributeBadge } from "@/components/primitives/attribute-badge";
import { Callout } from "@/components/primitives/callout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

/**
 * The Variables drawer: what this Workflow takes as input, and which Steps
 * stand on each of them.
 *
 * A Variable is declared inside the Draft document, so everything here is an
 * edit of that document and travels with the same save as the Steps do — a
 * rename is not a separate operation on a separate row, it is the document
 * again with one name changed and every value that reached for it rewritten.
 *
 * Two things a person can do here are refused rather than silently repaired.
 * Deleting a Variable a Step still uses would leave that value reaching for a
 * declaration that is gone, which is the document the store refuses; the
 * drawer says so, and says how many Steps are in the way, which a refusal
 * about a whole document cannot. A name the Workflow already declares is
 * refused for the same reason: a repeated name does not say what it declares.
 *
 * Activating a row's usage count closes the drawer, because what it does is
 * highlight the cards behind it — a modal panel over the thing it is pointing
 * at would be pointing at nothing.
 */
export function VariablesDrawer({
  open,
  document,
  onOpenChange,
  onChange,
  onShowUsages,
}: {
  open: boolean;
  document: WorkflowDocument;
  onOpenChange: (open: boolean) => void;
  onChange: (document: WorkflowDocument) => void;
  onShowUsages: (name: string) => void;
}) {
  const rows = variableRows(document);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="gap-0">
        <SheetHeader>
          <SheetTitle>Variables</SheetTitle>
          <SheetDescription>
            The inputs this Workflow takes. A Step value reaches for one as{" "}
            <code className="font-mono">{"{{name}}"}</code>, and a secret one is supplied per Run
            and never stored in a Step.
          </SheetDescription>
        </SheetHeader>

        <div className="flex flex-1 flex-col gap-2 overflow-y-auto px-4 pb-4">
          {rows.length === 0 ? (
            <p className="text-half text-mut">
              Nothing declared yet. Declare one here, or make one out of a value a recording
              captured, from the value field on its card.
            </p>
          ) : (
            rows.map((row) => (
              <VariableRowItem
                key={row.name}
                row={row}
                document={document}
                onChange={onChange}
                onShowUsages={(name) => {
                  onOpenChange(false);
                  onShowUsages(name);
                }}
              />
            ))
          )}
        </div>

        <SheetFooter className="border-t border-line">
          <DeclareForm document={document} onChange={onChange} />
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}

/** One declared Variable: its name, whether it is secret, and who stands on it. */
function VariableRowItem({
  row,
  document,
  onChange,
  onShowUsages,
}: {
  row: VariableRow;
  document: WorkflowDocument;
  onChange: (document: WorkflowDocument) => void;
  onShowUsages: (name: string) => void;
}) {
  const [typed, setTyped] = useState(row.name);
  const [refusal, setRefusal] = useState<string | null>(null);

  const rename = () => {
    if (typed === row.name) {
      setRefusal(null);
      return;
    }
    const refused = declarationRefusal(document, typed);
    setRefusal(refused);
    if (refused === null) {
      onChange(withVariableRenamed(document, row.name, typed));
    }
  };

  return (
    <div className="flex flex-col gap-2 rounded-md border border-line p-3">
      <div className="flex items-center gap-2">
        <Input
          aria-label={`Name of the Variable ${row.name}`}
          className="font-mono text-small"
          value={typed}
          onChange={(edited) => {
            setTyped(edited.target.value);
          }}
          onBlur={rename}
          onKeyDown={(pressed) => {
            if (pressed.key === "Enter") {
              rename();
            }
            if (pressed.key === "Escape") {
              setTyped(row.name);
              setRefusal(null);
            }
          }}
        />
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={`Delete the Variable ${row.name}`}
          title={`Delete the Variable ${row.name}`}
          className="text-mut hover:bg-bad-bg hover:text-bad"
          onClick={() => {
            const refused = deletionRefusal(document, row.name);
            setRefusal(refused);
            if (refused === null) {
              onChange(withVariableDeleted(document, row.name));
            }
          }}
        >
          <Trash2 className="size-4" />
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-half text-ink">
          <input
            type="checkbox"
            className="size-4 accent-human"
            checked={row.secret}
            onChange={(ticked) => {
              onChange(withVariableSecret(document, row.name, ticked.target.checked));
            }}
          />
          <KeyRound className="size-3.5 text-human" />
          Secret
        </label>

        {row.usedBy.length === 0 ? (
          <AttributeBadge tone="wait">unused</AttributeBadge>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            className="text-small text-mut"
            onClick={() => {
              onShowUsages(row.name);
            }}
          >
            {usage(row.usedBy.length)}
          </Button>
        )}
      </div>

      {refusal === null ? null : <Callout tone="warn">{refusal}</Callout>}
    </div>
  );
}

/** Declaring one by hand — the other way in is converting a value on a card. */
function DeclareForm({
  document,
  onChange,
}: {
  document: WorkflowDocument;
  onChange: (document: WorkflowDocument) => void;
}) {
  const [name, setName] = useState("");
  const [secret, setSecret] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);

  const declare = () => {
    const refused = declarationRefusal(document, name);
    setRefusal(refused);
    if (refused === null) {
      onChange(withVariableDeclared(document, { name, secret } satisfies Variable));
      setName("");
      setSecret(false);
    }
  };

  return (
    <form
      className="flex flex-col gap-2"
      onSubmit={(submitted) => {
        submitted.preventDefault();
        declare();
      }}
    >
      <Label htmlFor="new-variable" className="text-small font-semibold text-ink">
        Declare a Variable
      </Label>
      <div className="flex items-center gap-2">
        <Input
          id="new-variable"
          className="font-mono text-small"
          placeholder="tenant"
          autoComplete="off"
          value={name}
          onChange={(typed) => {
            setName(typed.target.value);
          }}
        />
        <Button type="submit" variant="secondary">
          Declare
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

/** "used by 1 step", counted in Steps rather than in references. */
function usage(steps: number): string {
  return `used by ${String(steps)} step${steps === 1 ? "" : "s"}`;
}
