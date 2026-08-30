import type { Variable } from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import { columnsOf, fillEveryRow, rowCounts } from "../../../../../../components/value-grid/grid";

import {
  addedVariables,
  createBody,
  creationDriftBanner,
  defaultBatchName,
  mergeVariables,
  progressHref,
  rerunBatchName,
  sequentialEta,
  submitBlockedByDrift,
} from "./creation";

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

describe("a Version that gained a Variable while the page is open", () => {
  it("names region on the banner and offers give every row the same value", () => {
    const added = addedVariables(["city"], [CITY, REGION, PASSWORD]);
    expect(added.map((variable) => variable.name)).toEqual(["region"]);
    const banner = creationDriftBanner(added);
    expect(banner?.name).toBe("region");
    expect(banner?.title).toMatch(/region/);
    expect(banner?.offer.toLowerCase()).toBe("give every row the same value");
  });

  it("does not treat a secret Variable or an already-loaded one as new", () => {
    expect(addedVariables(["city"], [CITY, PASSWORD])).toEqual([]);
    expect(creationDriftBanner([])).toBeNull();
  });

  it("fills the new column on every row with the one entered value", () => {
    const declared = mergeVariables([CITY], [REGION]);
    const columns = columnsOf(declared);
    const filled = fillEveryRow([{ city: "A" }, { city: "B" }], columns, "region", "EU");
    expect(filled).toEqual([
      { city: "A", region: "EU" },
      { city: "B", region: "EU" },
    ]);
    expect(createBody("Batch", filled, columns, false).rows).toEqual([
      { variables: { city: "A", region: "EU" } },
      { variables: { city: "B", region: "EU" } },
    ]);
  });

  it("blocks submit until the drift has been filled, so the POST is not sent", () => {
    expect(submitBlockedByDrift(addedVariables(["city"], [CITY, REGION]))).toBe(true);
    expect(submitBlockedByDrift([])).toBe(false);
  });
});
