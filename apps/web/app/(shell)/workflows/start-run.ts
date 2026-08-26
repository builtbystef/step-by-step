import type { Variable } from "@step-by-step/api-client";

import {
  submittedVariables,
  type GridColumn,
  type GridRow,
} from "../../../components/value-grid/grid";

/**
 * Starting a Run from the list row or the Workflow header.
 *
 * Immediate when the published Version declares no Variables; the one-row
 * value grid — secret Variables locked, never sent — when it declares some.
 * Both call sites share this so where you press Run cannot change what Run
 * does.
 */

export function needsValueGrid(variables: readonly Variable[]): boolean {
  return variables.length > 0;
}

export function startBody(
  row: GridRow,
  columns: readonly GridColumn[],
): { variables: Record<string, string> } {
  return { variables: submittedVariables(row, columns) };
}
