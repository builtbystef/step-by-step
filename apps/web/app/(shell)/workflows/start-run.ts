import type { Variable } from "@step-by-step/api-client";

import {
  submittedVariables,
  type GridColumn,
  type GridRow,
} from "../../../components/value-grid/grid";

export function needsValueGrid(variables: readonly Variable[]): boolean {
  return variables.length > 0;
}

export function startBody(
  row: GridRow,
  columns: readonly GridColumn[],
): { variables: Record<string, string> } {
  return { variables: submittedVariables(row, columns) };
}
