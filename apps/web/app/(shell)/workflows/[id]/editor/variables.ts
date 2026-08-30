import type { Variable, WorkflowDocument } from "@step-by-step/api-client";

import { interpolatedValue, withInterpolatedValue, type Step } from "./steps";

export const REFERENCE = /\{\{\s*([A-Za-z_][A-Za-z0-9_-]*)\s*\}\}/g;

export type VariableRow = {
  name: string;
  secret: boolean;
  usedBy: string[];
  secretId?: string;
  secretName?: string;
};

export type VaultSecret = { id: string; name: string };

export function referencesOf(step: Step): string[] {
  const value = interpolatedValue(step);
  if (value === null) {
    return [];
  }
  const names = [...value.matchAll(REFERENCE)].map(([, name]) => name ?? "");
  return [...new Set(names)];
}

export function variableRows(document: WorkflowDocument): VariableRow[] {
  const steps = document.steps ?? [];
  return (document.variables ?? []).map((variable: Variable) => ({
    name: variable.name,
    secret: variable.secret === true,
    usedBy: steps
      .filter((step) => referencesOf(step).includes(variable.name))
      .map((step) => step.id),
    ...pointerOf(variable),
  }));
}

export type UndeclaredRow = {
  name: string;
  usedBy: string[];
};

export function undeclaredNames(value: string, declared: readonly string[]): string[] {
  const known = new Set(declared);
  const names = [...value.matchAll(REFERENCE)].map(([, name]) => name ?? "");
  return [...new Set(names)].filter((name) => !known.has(name));
}

export function undeclaredRows(document: WorkflowDocument): UndeclaredRow[] {
  const declared = (document.variables ?? []).map((variable) => variable.name);
  const found = new Map<string, string[]>();
  for (const step of document.steps ?? []) {
    const value = interpolatedValue(step);
    if (value === null) {
      continue;
    }
    for (const name of undeclaredNames(value, declared)) {
      const usedBy = found.get(name);
      if (usedBy === undefined) {
        found.set(name, [step.id]);
      } else {
        usedBy.push(step.id);
      }
    }
  }
  return [...found.entries()].map(([name, usedBy]) => ({ name, usedBy }));
}

const VARIABLE_NAME = /^[A-Za-z_][A-Za-z0-9_-]*$/;

export function declarationRefusal(document: WorkflowDocument, name: string): string | null {
  if (!VARIABLE_NAME.test(name)) {
    return "A name starts with a letter or an underscore, and holds letters, digits, - and _.";
  }
  const taken = (document.variables ?? []).some((variable) => variable.name === name);
  return taken ? `This Workflow already declares ${name}.` : null;
}

export function withVariableDeclared(
  document: WorkflowDocument,
  variable: Variable,
): WorkflowDocument {
  return { ...document, variables: [...(document.variables ?? []), variable] };
}

export function deletionRefusal(document: WorkflowDocument, name: string): string | null {
  const used = variableRows(document).find((row) => row.name === name)?.usedBy ?? [];
  if (used.length === 0) {
    return null;
  }
  const steps = used.length === 1 ? "1 Step still uses" : `${String(used.length)} Steps still use`;
  return `${steps} {{${name}}}. Change those values first.`;
}

export function withVariableDeleted(document: WorkflowDocument, name: string): WorkflowDocument {
  return {
    ...document,
    variables: (document.variables ?? []).filter((variable) => variable.name !== name),
  };
}

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

export function withVariableSecret(
  document: WorkflowDocument,
  name: string,
  secret: boolean,
): WorkflowDocument {
  return {
    ...document,
    variables: (document.variables ?? []).map((variable) => {
      if (variable.name !== name) {
        return variable;
      }
      if (secret) {
        return { ...variable, secret: true };
      }
      return { name: variable.name, secret: false };
    }),
  };
}

function pointerOf(variable: Variable): Pick<VariableRow, "secretId" | "secretName"> {
  return {
    ...(typeof variable.secretId === "string" ? { secretId: variable.secretId } : {}),
    ...(typeof variable.secretName === "string" ? { secretName: variable.secretName } : {}),
  };
}

export function boundSecretName(
  variable: Pick<Variable, "secretId" | "secretName">,
  vault: readonly VaultSecret[],
): string | null {
  const id = variable.secretId;
  if (typeof id === "string") {
    const live = vault.find((entry) => entry.id === id);
    if (live !== undefined) {
      return live.name;
    }
  }
  return typeof variable.secretName === "string" ? variable.secretName : null;
}

export function withSecretBound(
  document: WorkflowDocument,
  name: string,
  secret: VaultSecret,
): WorkflowDocument {
  return {
    ...document,
    variables: (document.variables ?? []).map((variable) =>
      variable.name === name
        ? { ...variable, secret: true, secretId: secret.id, secretName: secret.name }
        : variable,
    ),
  };
}

export type Span = { from: number; to: number };

export function withReferenceInserted(value: string, name: string, at: number): string {
  const caret = Math.min(Math.max(at, 0), value.length);
  return `${value.slice(0, caret)}{{${name}}}${value.slice(caret)}`;
}

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

export function secretNames(document: WorkflowDocument): Set<string> {
  return new Set(
    (document.variables ?? []).filter((variable) => variable.secret === true).map((v) => v.name),
  );
}
