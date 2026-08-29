"use client";

import type { Variable, WorkflowDocument } from "@step-by-step/api-client";
import { KeyRound, Trash2 } from "lucide-react";
import { useState } from "react";

import {
  boundSecretName,
  declarationRefusal,
  deletionRefusal,
  undeclaredRows,
  variableRows,
  withSecretBound,
  withVariableDeclared,
  withVariableDeleted,
  withVariableRenamed,
  withVariableSecret,
  type UndeclaredRow,
  type VariableRow,
  type VaultSecret,
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
 * The other half of that rule is listed here too: a `{{name}}` a value
 * reaches for that nothing declares. Those rows sit in the amber that already
 * means look at this, name the Steps that use them, and offer a one-click
 * Declare it. A Draft with none of them shows no such section — absent, not
 * empty.
 *
 * Activating a row's usage count closes the drawer, because what it does is
 * highlight the cards behind it — a modal panel over the thing it is pointing
 * at would be pointing at nothing.
 *
 * A published Version's Variables are read: the rows sit in a disabled
 * fieldset, so nothing inside them can be renamed, unmasked, or deleted by a
 * control somebody forgets, and the form that declares a new one is gone —
 * declaring into a Version is not a thing to offer and refuse.
 */
export function VariablesDrawer({
  open,
  document,
  vault,
  readOnly,
  onOpenChange,
  onChange,
  onShowUsages,
}: {
  open: boolean;
  document: WorkflowDocument;
  vault: VaultSecret[];
  readOnly: boolean;
  onOpenChange: (open: boolean) => void;
  onChange: (document: WorkflowDocument) => void;
  onShowUsages: (name: string) => void;
}) {
  const rows = variableRows(document);
  const undeclared = undeclaredRows(document);

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

        <fieldset
          disabled={readOnly}
          className="flex min-w-0 flex-1 flex-col gap-2 overflow-y-auto px-4 pb-4"
        >
          {rows.length === 0 ? (
            <p className="text-half text-mut">
              {readOnly
                ? "This Version declares no Variables."
                : "Nothing declared yet. Declare one here, or make one out of a value a recording captured, from the value field on its card."}
            </p>
          ) : (
            rows.map((row) => (
              <VariableRowItem
                key={row.name}
                row={row}
                document={document}
                vault={vault}
                onChange={onChange}
                onShowUsages={(name) => {
                  onOpenChange(false);
                  onShowUsages(name);
                }}
              />
            ))
          )}
          {undeclared.length === 0 ? null : (
            <div className="flex flex-col gap-2">
              <p className="pt-2 text-small font-semibold text-ink">Not declared</p>
              {undeclared.map((row) => (
                <UndeclaredRowItem
                  key={row.name}
                  row={row}
                  document={document}
                  onChange={onChange}
                  onShowUsages={(name) => {
                    onOpenChange(false);
                    onShowUsages(name);
                  }}
                />
              ))}
            </div>
          )}
        </fieldset>

        {readOnly ? null : (
          <SheetFooter className="border-t border-line">
            <DeclareForm document={document} onChange={onChange} />
          </SheetFooter>
        )}
      </SheetContent>
    </Sheet>
  );
}

/** One declared Variable: its name, whether it is secret, and who stands on it. */
function VariableRowItem({
  row,
  document,
  vault,
  onChange,
  onShowUsages,
}: {
  row: VariableRow;
  document: WorkflowDocument;
  vault: VaultSecret[];
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

      {row.secret ? (
        <VaultPicker row={row} document={document} vault={vault} onChange={onChange} />
      ) : null}

      {refusal === null ? null : <Callout tone="warn">{refusal}</Callout>}
    </div>
  );
}

/** A `{{name}}` nothing declares: flagged amber, with the Steps that use it. */
function UndeclaredRowItem({
  row,
  document,
  onChange,
  onShowUsages,
}: {
  row: UndeclaredRow;
  document: WorkflowDocument;
  onChange: (document: WorkflowDocument) => void;
  onShowUsages: (name: string) => void;
}) {
  const [secret, setSecret] = useState(false);

  return (
    <div className="flex flex-col gap-2 rounded-md border border-wait/30 bg-wait-bg/40 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-small text-ink">{`{{${row.name}}}`}</span>
        <AttributeBadge tone="wait">undeclared</AttributeBadge>
      </div>

      <div className="flex flex-wrap items-center gap-3">
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
        <label className="flex items-center gap-2 text-half text-ink">
          <input
            type="checkbox"
            className="size-4 accent-human"
            checked={secret}
            onChange={(ticked) => {
              setSecret(ticked.target.checked);
            }}
          />
          <KeyRound className="size-3.5 text-human" />
          Secret
        </label>
        <Button
          variant="secondary"
          size="sm"
          className="text-small"
          onClick={() => {
            onChange(withVariableDeclared(document, { name: row.name, secret }));
          }}
        >
          Declare it
        </Button>
      </div>
    </div>
  );
}

/** Bind this secret Variable to a vault Secret, picked from the list. */
function VaultPicker({
  row,
  document,
  vault,
  onChange,
}: {
  row: VariableRow;
  document: WorkflowDocument;
  vault: VaultSecret[];
  onChange: (document: WorkflowDocument) => void;
}) {
  const shown = boundSecretName(row, vault);
  const live = vault.some((entry) => entry.id === row.secretId);
  const label = `Secret bound to {{${row.name}}}`;

  if (vault.length === 0) {
    return (
      <p className="text-small text-mut">
        {shown === null
          ? "Create a Secret in Settings to bind one."
          : `Bound to ${shown}, which is no longer in the vault.`}
      </p>
    );
  }

  return (
    <label className="flex min-w-0 flex-col gap-1 text-small text-mut">
      Vault Secret
      <select
        aria-label={label}
        className="h-9 rounded-md border border-line bg-panel px-2 text-half text-ink"
        value={live ? (row.secretId ?? "") : ""}
        onChange={(chosen) => {
          const picked = vault.find((entry) => entry.id === chosen.target.value);
          if (picked !== undefined) {
            onChange(withSecretBound(document, row.name, picked));
          }
        }}
      >
        {live ? null : (
          <option value="">{shown === null ? "Bind to a Secret…" : `${shown} (deleted)`}</option>
        )}
        {vault.map((entry) => (
          <option key={entry.id} value={entry.id}>
            {entry.name}
          </option>
        ))}
      </select>
    </label>
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
