import type { Variable } from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import {
  applyCopiedBatch,
  applyPaste,
  blankRows,
  columnsOf,
  lockedCellLabel,
  parseSpreadsheet,
  rowCounts,
  setCell,
  submittedVariables,
} from "./grid";

const CITY: Variable = { name: "city" };
const REGION: Variable = { name: "region" };
const PASSWORD: Variable = {
  name: "password",
  secret: true,
  secretId: "sec-1",
  secretName: "acme-portal-password",
};

function variables(...declared: Variable[]): Variable[] {
  return declared;
}

describe("the grid's columns", () => {
  it("follow declaration order, with the secret column locked and reading from vault", () => {
    const columns = columnsOf(variables(CITY, PASSWORD, REGION));

    expect(columns.map((column) => column.name)).toEqual(["city", "password", "region"]);
    expect(columns.map((column) => column.secret)).toEqual([false, true, false]);
    expect(lockedCellLabel(columns[1]!)).toBe("from vault · acme-portal-password");
  });

  it("still reads from vault when the Secret's cached name is all that remains", () => {
    const columns = columnsOf([{ name: "password", secret: true, secretName: "old-name" }]);
    expect(lockedCellLabel(columns[0]!)).toBe("from vault · old-name");
  });
});

describe("typing a cell", () => {
  it("writes cell by cell into a non-secret column, and refuses the secret column", () => {
    const columns = columnsOf(variables(CITY, PASSWORD, REGION));
    const [row] = blankRows(columns, 1);
    expect(row).toEqual({ city: "", region: "" });

    const typed = setCell(row!, columns, "city", "Belgrade");
    expect(typed).toEqual({ city: "Belgrade", region: "" });

    const refused = setCell(typed, columns, "password", "hunter2");
    expect(refused).toEqual({ city: "Belgrade", region: "" });
    expect(refused).not.toHaveProperty("password");
  });
});

describe("pasting a spreadsheet table", () => {
  it("splits a multi-row, multi-column TSV into rows and cells", () => {
    expect(parseSpreadsheet("Belgrade\tEU\nLyon\tEU")).toEqual([
      ["Belgrade", "EU"],
      ["Lyon", "EU"],
    ]);
  });

  it("lands the split table on the grid from the starting cell, adding rows", () => {
    const columns = columnsOf(variables(CITY, REGION));
    const rows = blankRows(columns, 1);
    const next = applyPaste(rows, columns, 0, 0, [
      ["Belgrade", "EU"],
      ["Lyon", "EU"],
    ]);

    expect(next).toEqual([
      { city: "Belgrade", region: "EU" },
      { city: "Lyon", region: "EU" },
    ]);
  });

  it("never writes a pasted value into the secret column", () => {
    const columns = columnsOf(variables(CITY, PASSWORD, REGION));
    const next = applyPaste(blankRows(columns, 1), columns, 0, 0, [["Belgrade", "stolen", "EU"]]);

    expect(next).toEqual([{ city: "Belgrade", region: "EU" }]);
    expect(next[0]).not.toHaveProperty("password");
  });
});

describe("copying rows from a past Batch", () => {
  it("lands the past Batch's non-secret values in declaration order", () => {
    const columns = columnsOf(variables(CITY, PASSWORD, REGION));
    const next = applyCopiedBatch(columns, [
      { variables: { city: "Belgrade", region: "EU", password: "stolen" } },
      { variables: { city: "Lyon" } },
    ]);

    expect(next).toEqual([
      { city: "Belgrade", region: "EU" },
      { city: "Lyon", region: "" },
    ]);
    expect(next[0]).not.toHaveProperty("password");
  });
});

describe("the submitted payload", () => {
  it("carries nothing for the secret Variable", () => {
    const columns = columnsOf(variables(CITY, PASSWORD, REGION));
    const row = { city: "Belgrade", region: "EU", password: "stolen" };
    expect(submittedVariables(row, columns)).toEqual({ city: "Belgrade", region: "EU" });
  });
});

describe("footer counts", () => {
  it("counts 5 rows of which 2 miss a value as total 5, complete 3, missing 2", () => {
    const columns = columnsOf(variables(CITY, REGION));
    const rows = [
      { city: "A", region: "EU" },
      { city: "B", region: "EU" },
      { city: "C", region: "EU" },
      { city: "D", region: "" },
      { city: "", region: "EU" },
    ];
    expect(rowCounts(rows, columns)).toEqual({ total: 5, complete: 3, missing: 2 });
  });
});

describe("one fixed row, for the Schedule and run-start consumers", () => {
  it("keeps a single row and the same locked secret cell", () => {
    const columns = columnsOf(variables(CITY, PASSWORD));
    const rows = blankRows(columns, 1);
    expect(rows).toHaveLength(1);
    expect(lockedCellLabel(columns[1]!)).toBe("from vault · acme-portal-password");

    const pasted = applyPaste(rows, columns, 0, 0, [["Belgrade"], ["Lyon"]], { fixedRowCount: 1 });
    expect(pasted).toHaveLength(1);
    expect(pasted[0]).toEqual({ city: "Belgrade" });
  });
});
