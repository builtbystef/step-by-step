import type { DraftState, Variable } from "@step-by-step/api-client";

/**
 * Starting a test Run of the Draft: one field per declared Variable, secret
 * ones masked, and never blocked by publishing.
 *
 * A test Run snapshots the Draft as it stands and mints no Version, so a
 * Workflow nobody has published can still verify its edits. Secret values
 * stay in the vault — the form asks for them so every Variable is present
 * and masked, and the payload never carries them.
 */

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

/**
 * Why a test run cannot start, or nothing when it can.
 *
 * Publishing has no say: the shared sentence that blocks Run / New batch /
 * New schedule is about a Version, and a test Run does not need one. Unsaved
 * editor changes do: the snapshot is the server Draft, and starting against
 * a dirty local copy would test something the person is not looking at.
 */
export function testRunRefusal(_state: DraftState, unsaved: boolean): string | null {
  return unsaved ? "Save or discard your editor changes before a test run." : null;
}
