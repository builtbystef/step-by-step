import type { Variable } from "@step-by-step/api-client";

export type GridColumn = {
  name: string;
  secret: boolean;
  secretName: string | null;
};

export type GridRow = Record<string, string>;

export function columnsOf(variables: readonly Variable[]): GridColumn[] {
  return variables.map((variable) => ({
    name: variable.name,
    secret: variable.secret === true,
    secretName: typeof variable.secretName === "string" ? variable.secretName : null,
  }));
}

export function lockedCellLabel(column: GridColumn): string {
  return column.secretName === null ? "from vault" : `from vault · ${column.secretName}`;
}

export function emptyRow(columns: readonly GridColumn[]): GridRow {
  const row: GridRow = {};
  for (const column of columns) {
    if (!column.secret) {
      row[column.name] = "";
    }
  }
  return row;
}

export function blankRows(columns: readonly GridColumn[], count: number): GridRow[] {
  return Array.from({ length: count }, () => emptyRow(columns));
}

export function setCell(
  row: GridRow,
  columns: readonly GridColumn[],
  name: string,
  value: string,
): GridRow {
  const column = columns.find((entry) => entry.name === name);
  if (column === undefined || column.secret) {
    return row;
  }
  return { ...row, [name]: value };
}

export function parseSpreadsheet(text: string): string[][] {
  const normalized = text.replaceAll("\r\n", "\n").replaceAll("\r", "\n");
  const trimmed = normalized.endsWith("\n") ? normalized.slice(0, -1) : normalized;
  if (trimmed === "") {
    return [];
  }
  return trimmed.split("\n").map((line) => line.split("\t"));
}

export function applyPaste(
  rows: readonly GridRow[],
  columns: readonly GridColumn[],
  startRow: number,
  startCol: number,
  table: readonly (readonly string[])[],
  options?: { fixedRowCount?: number },
): GridRow[] {
  const next = rows.map((row) => ({ ...row }));
  const cap = options?.fixedRowCount;

  for (const [tableRow, cells] of table.entries()) {
    const rowIndex = startRow + tableRow;
    if (cap !== undefined && rowIndex >= cap) {
      break;
    }
    while (next.length <= rowIndex) {
      next.push(emptyRow(columns));
    }
    let current = next[rowIndex] ?? emptyRow(columns);
    for (const [tableCol, value] of cells.entries()) {
      const column = columns[startCol + tableCol];
      if (column === undefined) {
        continue;
      }
      current = setCell(current, columns, column.name, value);
    }
    next[rowIndex] = current;
  }

  return cap === undefined ? next : next.slice(0, cap);
}

export function applyCopiedBatch(
  columns: readonly GridColumn[],
  pastRows: readonly { variables: Record<string, unknown> }[],
): GridRow[] {
  return pastRows.map((past) => {
    let row = emptyRow(columns);
    for (const column of columns) {
      if (column.secret) {
        continue;
      }
      row = setCell(row, columns, column.name, scalarValue(past.variables[column.name]));
    }
    return row;
  });
}

export function fillEveryRow(
  rows: readonly GridRow[],
  columns: readonly GridColumn[],
  name: string,
  value: string,
): GridRow[] {
  return rows.map((row) => setCell(row, columns, name, value));
}

export function submittedVariables(
  row: GridRow,
  columns: readonly GridColumn[],
): Record<string, string> {
  const variables: Record<string, string> = {};
  for (const column of columns) {
    if (!column.secret) {
      variables[column.name] = row[column.name] ?? "";
    }
  }
  return variables;
}

export function rowCounts(
  rows: readonly GridRow[],
  columns: readonly GridColumn[],
): { total: number; complete: number; missing: number } {
  const required = columns.filter((column) => !column.secret).map((column) => column.name);
  let complete = 0;
  let missing = 0;
  for (const row of rows) {
    const incomplete = required.some((name) => (row[name] ?? "").trim() === "");
    if (incomplete) {
      missing += 1;
    } else {
      complete += 1;
    }
  }
  return { total: rows.length, complete, missing };
}

function scalarValue(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return "";
}
