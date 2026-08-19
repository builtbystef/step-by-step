import type { Variable, WorkflowDocument } from "@step-by-step/api-client";

import { interpolatedValue, withInterpolatedValue, type Step } from "./steps";

/**
 * Variables as the drawer edits them: declared inside the Draft document,
 * referenced by name from the values that interpolate them.
 *
 * The rules here are the document store's, brought forward to where a person
 * is working. The store refuses a document whose value names a Variable it
 * does not declare — that is what makes deleting a used Variable impossible —
 * and refusing it in the drawer instead says which Steps stand in the way,
 * before a save comes back with a sentence about a document.
 */

export const REFERENCE = /\{\{\s*([A-Za-z_][A-Za-z0-9_-]*)\s*\}\}/g;
/** A Variable reference inside a value, as the document store reads one. */

/** One row of the drawer: the declaration, and the Steps standing on it. */
export type VariableRow = {
  name: string;
  secret: boolean;
  /** The ids of the Steps whose value names it, in the order the list runs. */
  usedBy: string[];
};

/** The names this Step's value interpolates, each one once. */
export function referencesOf(step: Step): string[] {
  const value = interpolatedValue(step);
  if (value === null) {
    return [];
  }
  const names = [...value.matchAll(REFERENCE)].map(([, name]) => name ?? "");
  return [...new Set(names)];
}

/** Every declared Variable, with the Steps that use it. */
export function variableRows(document: WorkflowDocument): VariableRow[] {
  const steps = document.steps ?? [];
  return (document.variables ?? []).map((variable: Variable) => ({
    name: variable.name,
    secret: variable.secret === true,
    usedBy: steps
      .filter((step) => referencesOf(step).includes(variable.name))
      .map((step) => step.id),
  }));
}

const VARIABLE_NAME = /^[A-Za-z_][A-Za-z0-9_-]*$/;
/** What a Variable may be called, and therefore what `{{name}}` may hold. */

/**
 * Why this name cannot be declared, or null when it can.
 *
 * Both reasons are the document store's, said before the save rather than
 * after it: a name outside the pattern is one no `{{name}}` could reach, and
 * a repeated name does not say what it declares — which of the two rows a
 * reader picked would decide whether the value is masked. Names are compared
 * as written, never folded, so `Password` and `password` are two Variables.
 */
export function declarationRefusal(document: WorkflowDocument, name: string): string | null {
  if (!VARIABLE_NAME.test(name)) {
    return "A name starts with a letter or an underscore, and holds letters, digits, - and _.";
  }
  const taken = (document.variables ?? []).some((variable) => variable.name === name);
  return taken ? `This Workflow already declares ${name}.` : null;
}

/** The document with one more Variable declared in it. */
export function withVariableDeclared(
  document: WorkflowDocument,
  variable: Variable,
): WorkflowDocument {
  return { ...document, variables: [...(document.variables ?? []), variable] };
}

/**
 * Why this Variable cannot be deleted, or null when it can.
 *
 * A Step whose value names it would be left reaching for a declaration that
 * is gone, and that document is one the store refuses. Saying so here names
 * the Steps in the way, which a refusal about the whole document cannot.
 */
export function deletionRefusal(document: WorkflowDocument, name: string): string | null {
  const used = variableRows(document).find((row) => row.name === name)?.usedBy ?? [];
  if (used.length === 0) {
    return null;
  }
  const steps = used.length === 1 ? "1 Step still uses" : `${String(used.length)} Steps still use`;
  return `${steps} {{${name}}}. Change those values first.`;
}

/** The document without that Variable. The Steps are untouched. */
export function withVariableDeleted(document: WorkflowDocument, name: string): WorkflowDocument {
  return {
    ...document,
    variables: (document.variables ?? []).filter((variable) => variable.name !== name),
  };
}

/**
 * The document under a new name for one Variable — declaration and every
 * reference to it, in one edit.
 *
 * Renaming only the declaration would leave every value that uses it reaching
 * for a name nothing declares, which is the document the store refuses. So a
 * rename rewrites the values as well, and because it is one document saved
 * whole, every card that reads that value reads the new name.
 */
export function withVariableRenamed(
  document: WorkflowDocument,
  from: string,
  to: string,
): WorkflowDocument {
  return {
    ...document,
    variables: (document.variables ?? []).map((variable) =>
      variable.name === from ? { ...variable, name: to } : variable,
    ),
    steps: (document.steps ?? []).map((step) => {
      const value = interpolatedValue(step);
      if (value === null || !referencesOf(step).includes(from)) {
        return step;
      }
      return withInterpolatedValue(
        step,
        value.replace(REFERENCE, (found, name: string) => (name === from ? `{{${to}}}` : found)),
      );
    }),
  };
}

/**
 * The document with one Variable's secret flag set.
 *
 * Masking keys off this flag and never off the syntax, so re-flagging is all
 * it takes to make a value stop being shown — the `{{name}}` in the values
 * that use it does not change, and does not need to.
 */
export function withVariableSecret(
  document: WorkflowDocument,
  name: string,
  secret: boolean,
): WorkflowDocument {
  return {
    ...document,
    variables: (document.variables ?? []).map((variable) =>
      variable.name === name ? { ...variable, secret } : variable,
    ),
  };
}

/** A run of characters inside a value: what the person had selected. */
export type Span = { from: number; to: number };

/**
 * A value with `{{name}}` written into it at the caret.
 *
 * Insertion rather than replacement, because a value mixes literal text and
 * Variables freely — a URL is usually a host with one Variable in the middle
 * of it, not a Variable on its own.
 */
export function withReferenceInserted(value: string, name: string, at: number): string {
  const caret = Math.min(Math.max(at, 0), value.length);
  return `${value.slice(0, caret)}{{${name}}}${value.slice(caret)}`;
}

/**
 * A literal a recording captured, made into a Variable: declared, and
 * replaced in the value by a reference to it.
 *
 * The two halves are one edit because either alone is a document the store
 * refuses or a Variable nothing uses — and because the person is doing one
 * thing: this typed-in account name is an input, not part of the automation.
 */
export function withLiteralMadeVariable(
  document: WorkflowDocument,
  stepId: string,
  variable: Variable,
  span: Span,
): WorkflowDocument {
  const declared = withVariableDeclared(document, variable);
  return {
    ...declared,
    steps: (declared.steps ?? []).map((step) => {
      const value = interpolatedValue(step);
      if (step.id !== stepId || value === null) {
        return step;
      }
      return withInterpolatedValue(
        step,
        `${value.slice(0, span.from)}{{${variable.name}}}${value.slice(span.to)}`,
      );
    }),
  };
}

/**
 * The names that are declared secret.
 *
 * A pill is drawn from this and never from the name: a Variable called
 * `secret_note` is a plain one, and a Variable called `t` can be the
 * password. The flag is the only thing that decides masking.
 */
export function secretNames(document: WorkflowDocument): Set<string> {
  return new Set(
    (document.variables ?? []).filter((variable) => variable.secret === true).map((v) => v.name),
  );
}
