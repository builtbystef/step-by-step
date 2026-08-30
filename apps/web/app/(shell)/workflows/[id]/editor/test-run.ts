import type { DraftState, Variable } from "@step-by-step/api-client";

export type TestRunField = {
  name: string;
  secret: boolean;
};

export function testRunFields(variables: readonly Variable[]): TestRunField[] {
  return variables.map((variable) => ({
    name: variable.name,
    secret: variable.secret === true,
  }));
}

export function testRunBody(
  values: Record<string, string>,
  fields: readonly TestRunField[],
): { test: true; variables: Record<string, string> } {
  const variables: Record<string, string> = {};
  for (const field of fields) {
    if (!field.secret) {
      variables[field.name] = values[field.name] ?? "";
    }
  }
  return { test: true, variables };
}

export function testRunRefusal(_state: DraftState, unsaved: boolean): string | null {
  return unsaved ? "Save or discard your editor changes before a test run." : null;
}
