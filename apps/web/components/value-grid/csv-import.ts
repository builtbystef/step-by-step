import { reconcile, type MappingEntry } from "../../lib/reconcile";

import { emptyRow, setCell, type GridColumn, type GridRow } from "./grid";

/**
 * Client-side CSV import: parse in the browser, reconcile, land when
 * confident, otherwise wait on the mapping strip. The file never leaves
 * this module, and a dropped secret column's values never become a cell.
 */

export type ParsedCsv = {
  headers: string[];
  rows: string[][];
};

export type ImportAssignment = MappingEntry;

export type SummaryPanel = {
  kind: "summary";
  dismissed: boolean;
  matched: { variableName: string; header: string }[];
  ignoredHeaders: string[];
  droppedSecretHeaders: string[];
  parsed: ParsedCsv;
  assignment: ImportAssignment[];
};

export type StripPanel = {
  kind: "strip";
  headers: string[];
  assignment: ImportAssignment[];
  droppedSecretHeaders: string[];
  parsed: ParsedCsv;
};

export type ImportPanel = { kind: "idle" } | StripPanel | SummaryPanel;

export type ImportOutcome =
  | { kind: "landed"; rows: GridRow[]; panel: SummaryPanel }
  | { kind: "strip"; panel: StripPanel };

const DELIMITERS = [",", "\t", ";", "|"] as const;

export function parseCsv(text: string): ParsedCsv {
  const input = text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
  const delimiter = sniffDelimiter(input);
  const table = parseTable(input, delimiter).filter((row) => row.some((cell) => cell !== ""));
  const headers = table[0] ?? [];
  const rows = table.slice(1).map((row) => headers.map((_, index) => row[index] ?? ""));
  return { headers, rows };
}

export function beginImport(
  text: string,
  variables: readonly { name: string; secret?: boolean }[],
  columns: readonly GridColumn[],
  options?: { fixedRowCount?: number },
): ImportOutcome {
  const parsed = parseCsv(text);
  const result = reconcile(parsed.headers, variables);
  if (result.confident) {
    return {
      kind: "landed",
      rows: applyImport(parsed, result.mapping, columns, options),
      panel: toSummary(parsed, result.mapping, result.ignoredHeaders, result.droppedSecretHeaders),
    };
  }
  return {
    kind: "strip",
    panel: {
      kind: "strip",
      headers: parsed.headers,
      assignment: result.mapping,
      droppedSecretHeaders: result.droppedSecretHeaders,
      parsed,
    },
  };
}

export function confirmImport(
  panel: StripPanel,
  columns: readonly GridColumn[],
  options?: { fixedRowCount?: number },
): { rows: GridRow[]; panel: SummaryPanel } {
  const assigned = new Set(
    panel.assignment
      .map((entry) => entry.header)
      .filter((header): header is string => header !== null),
  );
  const ignoredHeaders = panel.headers.filter(
    (header) => !assigned.has(header) && !panel.droppedSecretHeaders.includes(header),
  );
  return {
    rows: applyImport(panel.parsed, panel.assignment, columns, options),
    panel: toSummary(panel.parsed, panel.assignment, ignoredHeaders, panel.droppedSecretHeaders),
  };
}

export function assignHeader(
  panel: StripPanel,
  variableName: string,
  header: string | null,
): StripPanel {
  return {
    ...panel,
    assignment: panel.assignment.map((entry) =>
      entry.variableName === variableName ? { ...entry, header, suggested: false } : entry,
    ),
  };
}

export function dismissSummary(panel: SummaryPanel): SummaryPanel {
  return { ...panel, dismissed: true };
}

export function reopenSummary(panel: SummaryPanel): SummaryPanel {
  return { ...panel, dismissed: false };
}

export function stripFromSummary(panel: SummaryPanel): StripPanel {
  return {
    kind: "strip",
    headers: panel.parsed.headers,
    assignment: panel.assignment,
    droppedSecretHeaders: panel.droppedSecretHeaders,
    parsed: panel.parsed,
  };
}

/** Headers the strip may map — dropped secret columns are not offered. */
export function mappableHeaders(panel: StripPanel): string[] {
  return panel.headers.filter((header) => !panel.droppedSecretHeaders.includes(header));
}

export function applyImport(
  parsed: ParsedCsv,
  assignment: readonly ImportAssignment[],
  columns: readonly GridColumn[],
  options?: { fixedRowCount?: number },
): GridRow[] {
  const indexByHeader = new Map<string, number>();
  for (const [index, header] of parsed.headers.entries()) {
    if (!indexByHeader.has(header)) {
      indexByHeader.set(header, index);
    }
  }
  const source =
    options?.fixedRowCount === undefined
      ? parsed.rows
      : parsed.rows.slice(0, options.fixedRowCount);
  return source.map((cells) => {
    let row = emptyRow(columns);
    for (const entry of assignment) {
      if (entry.header === null) {
        continue;
      }
      const index = indexByHeader.get(entry.header);
      if (index === undefined) {
        continue;
      }
      row = setCell(row, columns, entry.variableName, cells[index] ?? "");
    }
    return row;
  });
}

function toSummary(
  parsed: ParsedCsv,
  assignment: readonly ImportAssignment[],
  ignoredHeaders: readonly string[],
  droppedSecretHeaders: readonly string[],
): SummaryPanel {
  return {
    kind: "summary",
    dismissed: false,
    matched: assignment
      .filter((entry): entry is ImportAssignment & { header: string } => entry.header !== null)
      .map((entry) => ({ variableName: entry.variableName, header: entry.header })),
    ignoredHeaders: [...ignoredHeaders],
    droppedSecretHeaders: [...droppedSecretHeaders],
    parsed,
    assignment: [...assignment],
  };
}

function sniffDelimiter(text: string): string {
  let best: string = ",";
  let bestScore = -1;
  for (const delimiter of DELIMITERS) {
    const rows = parseTable(text, delimiter)
      .filter((row) => row.some((cell) => cell !== ""))
      .slice(0, 10);
    if (rows.length === 0) {
      continue;
    }
    const width = rows[0]?.length ?? 0;
    const consistent = rows.every((row) => row.length === width);
    const score = consistent ? width * rows.length : 0;
    if (score > bestScore) {
      best = delimiter;
      bestScore = score;
    }
  }
  return best;
}

function parseTable(text: string, delimiter: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index]!;
    if (quoted) {
      if (char === '"') {
        if (text[index + 1] === '"') {
          field += '"';
          index += 1;
        } else {
          quoted = false;
        }
      } else {
        field += char;
      }
      continue;
    }
    if (char === '"') {
      quoted = true;
      continue;
    }
    if (char === delimiter) {
      row.push(field);
      field = "";
      continue;
    }
    if (char === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
      continue;
    }
    if (char === "\r") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
      if (text[index + 1] === "\n") {
        index += 1;
      }
      continue;
    }
    field += char;
  }
  if (quoted || field !== "" || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}
