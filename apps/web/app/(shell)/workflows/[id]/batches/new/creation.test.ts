import type { Variable } from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import { columnsOf, rowCounts } from "../../../../../../components/value-grid/grid";

import {
  createBody,
  defaultBatchName,
  progressHref,
  rerunBatchName,
  sequentialEta,
} from "./creation";

/**
 * The Batch creation page's decisions, read back without a DOM: the default
 * name, the copy-from-a-past-Batch name, the incomplete-row flag on the
 * payload, the sequential ETA, and where submit navigates.
 */

const CITY: Variable = { name: "city" };
const PASSWORD: Variable = {
  name: "password",
  secret: true,
  secretId: "sec-1",
  secretName: "acme-portal-password",
};
const REGION: Variable = { name: "region" };

describe("the Batch name", () => {
  it("defaults to the Workflow name and the date", () => {
    expect(defaultBatchName("Invoice scraper", new Date(2026, 7, 26))).toBe(
      "Invoice scraper — 26 Aug 2026",
    );
  });

  it("becomes a rerun name when the rows were copied from a past Batch", () => {
    expect(rerunBatchName("Invoice scraper", "July invoices")).toBe(
      "Invoice scraper — rerun of July invoices",
    );
  });
});

describe("the incomplete-row checkbox", () => {
  it("submits run_incomplete_rows false when unchecked, true when checked", () => {
    const columns = columnsOf([CITY, PASSWORD, REGION]);
    const rows = [
      { city: "A", region: "EU" },
      { city: "B", region: "" },
    ];

    expect(createBody("Batch", rows, columns, false)).toEqual({
      name: "Batch",
      run_incomplete_rows: false,
      rows: [{ variables: { city: "A", region: "EU" } }, { variables: { city: "B", region: "" } }],
    });
    expect(createBody("Batch", rows, columns, true).run_incomplete_rows).toBe(true);
    expect(createBody("Batch", rows, columns, false).rows?.[0]?.variables).not.toHaveProperty(
      "password",
    );
  });
});

describe("the sequential ETA", () => {
  it("shows an 18-minute ETA for a 90 s median and 12 rows", () => {
    expect(sequentialEta(12, 90_000)).toBe("about 18 min");
  });

  it("shows 12 Runs, one at a time and no time when there is no median", () => {
    expect(sequentialEta(12, null)).toBe("12 Runs, one at a time");
    expect(sequentialEta(12, undefined)).toBe("12 Runs, one at a time");
  });
});

describe("submit", () => {
  it("navigates to the Batch's progress view", () => {
    expect(progressHref("bat-9")).toBe("/batches/bat-9");
  });
});

describe("footer counts on the creation body", () => {
  it("agrees with the grid: 5 rows, 3 complete, 2 missing", () => {
    const columns = columnsOf([CITY, REGION]);
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
