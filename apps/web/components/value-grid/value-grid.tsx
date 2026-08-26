"use client";

import type { Variable } from "@step-by-step/api-client";
import { Plus } from "lucide-react";
import type { ClipboardEvent } from "react";

import {
  applyPaste,
  blankRows,
  columnsOf,
  emptyRow,
  parseSpreadsheet,
  setCell,
  type GridRow,
} from "./grid";

import { LockedCell } from "@/components/primitives/locked-cell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/**
 * The one value grid: N rows for a Batch, one row for a Schedule or a
 * run-start. Secret columns are locked, headed with the Variable's name,
 * and never sent.
 */

export function ValueGrid({
  variables,
  rows,
  onChange,
  fixedRowCount,
}: {
  variables: readonly Variable[];
  rows: readonly GridRow[];
  onChange: (rows: GridRow[]) => void;
  /** When set, the grid cannot grow or shrink. Schedules and run-start pass 1. */
  fixedRowCount?: number;
}) {
  const columns = columnsOf(variables);

  const pasteAt = (row: number, col: number, event: ClipboardEvent<HTMLInputElement>) => {
    const text = event.clipboardData.getData("text/plain");
    if (!text.includes("\t") && !text.includes("\n") && !text.includes("\r")) {
      return;
    }
    event.preventDefault();
    onChange(applyPaste(rows, columns, row, col, parseSpreadsheet(text), { fixedRowCount }));
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="overflow-auto">
        <table className="w-full text-left text-half">
          <thead>
            <tr className="text-micro text-mut">
              <th className="w-8 px-2 py-1 font-semibold">#</th>
              {columns.map((column) => (
                <th key={column.name} className="px-2 py-1 font-semibold">
                  {column.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex} className="border-t border-line">
                <td className="px-2 py-1 font-mono text-micro text-mut">{String(rowIndex + 1)}</td>
                {columns.map((column, colIndex) => (
                  <td key={column.name} className="px-2 py-1">
                    {column.secret ? (
                      <span className="flex items-center gap-1.5">
                        <span className="text-half text-mut">from vault</span>
                        {column.secretName === null ? null : (
                          <LockedCell secretName={column.secretName} />
                        )}
                      </span>
                    ) : (
                      <Input
                        aria-label={`${column.name} row ${String(rowIndex + 1)}`}
                        value={row[column.name] ?? ""}
                        autoComplete="off"
                        className="h-7 font-mono text-half"
                        onChange={(typed) => {
                          const next = rows.map((entry, index) =>
                            index === rowIndex
                              ? setCell(entry, columns, column.name, typed.target.value)
                              : entry,
                          );
                          onChange(next);
                        }}
                        onPaste={(event) => {
                          pasteAt(rowIndex, colIndex, event);
                        }}
                      />
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {fixedRowCount === undefined ? (
        <div className="flex justify-start">
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => {
              onChange([...rows, emptyRow(columns)]);
            }}
          >
            <Plus className="size-3.5" />
            Add row
          </Button>
        </div>
      ) : null}
    </div>
  );
}

/** One empty row of this Workflow's Variables, for first paint and one-row consumers. */
export function initialRows(variables: readonly Variable[], count: number = 1): GridRow[] {
  return blankRows(columnsOf(variables), count);
}
