import type { Variable } from "@step-by-step/api-client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { beginImport, confirmImport, dismissSummary, parseCsv, reopenSummary } from "./csv-import";
import { columnsOf, submittedVariables } from "./grid";

const CITY: Variable = { name: "city" };
const ZIP_CODE: Variable = { name: "zipCode" };
const PASSWORD: Variable = {
  name: "password",
  secret: true,
  secretId: "sec-1",
  secretName: "acme-portal-password",
};

const MESSY_CSV = `City,notes
"Paris, TX","He said ""hello"",
then left"
Lyon,quiet
`;

const CONFIDENT_CSV = `City,zip_code,notes,password
Belgrade,11000,capital,hunter2
Lyon,69000,quiet,hunter2
`;

const UNCERTAIN_CSV = `cite,zip
Belgrade,11000
`;

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("parsing a messy CSV", () => {
  it("keeps quoted commas and newlines inside the cell they belong to", () => {
    expect(parseCsv(MESSY_CSV)).toEqual({
      headers: ["City", "notes"],
      rows: [
        ["Paris, TX", 'He said "hello",\nthen left'],
        ["Lyon", "quiet"],
      ],
    });
  });
});

describe("a confident file", () => {
  it("lands rows without a strip, names matched ignored and dropped, and the summary reopens", () => {
    const columns = columnsOf([CITY, ZIP_CODE, PASSWORD]);
    const outcome = beginImport(CONFIDENT_CSV, [CITY, ZIP_CODE, PASSWORD], columns);

    expect(outcome.kind).toBe("landed");
    if (outcome.kind !== "landed") {
      return;
    }
    expect(outcome.rows).toEqual([
      { city: "Belgrade", zipCode: "11000" },
      { city: "Lyon", zipCode: "69000" },
    ]);
    expect(outcome.panel.kind).toBe("summary");
    if (outcome.panel.kind !== "summary") {
      return;
    }
    expect(outcome.panel.dismissed).toBe(false);
    expect(outcome.panel.matched).toEqual([
      { variableName: "city", header: "City" },
      { variableName: "zipCode", header: "zip_code" },
    ]);
    expect(outcome.panel.ignoredHeaders).toEqual(["notes"]);
    expect(outcome.panel.droppedSecretHeaders).toEqual(["password"]);

    const dismissed = dismissSummary(outcome.panel);
    expect(dismissed.dismissed).toBe(true);
    expect(reopenSummary(dismissed).dismissed).toBe(false);
  });
});

describe("a not-confident file", () => {
  it("shows the mapping strip with real names and unconfirmed suggestions; rows land on confirm", () => {
    const columns = columnsOf([CITY, ZIP_CODE]);
    const outcome = beginImport(UNCERTAIN_CSV, [CITY, ZIP_CODE], columns);

    expect(outcome.kind).toBe("strip");
    if (outcome.kind !== "strip") {
      return;
    }
    expect(outcome.panel.headers).toEqual(["cite", "zip"]);
    expect(outcome.panel.assignment).toEqual([
      { variableName: "city", header: "cite", suggested: true },
      { variableName: "zipCode", header: "zip", suggested: true },
    ]);

    const confirmed = confirmImport(outcome.panel, columns);
    expect(confirmed.rows).toEqual([{ city: "Belgrade", zipCode: "11000" }]);
    expect(confirmed.panel.kind).toBe("summary");
  });
});

describe("the file stays in the browser", () => {
  it("makes no network request that carries the file or a dropped column's values", () => {
    const requests: string[] = [];
    vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : String(input);
      const body =
        typeof init?.body === "string"
          ? init.body
          : input instanceof Request
            ? await input.clone().text()
            : "";
      requests.push(`${url}\n${body}`);
      return new Response("unexpected", { status: 599 });
    });

    const columns = columnsOf([CITY, ZIP_CODE, PASSWORD]);
    const outcome = beginImport(CONFIDENT_CSV, [CITY, ZIP_CODE, PASSWORD], columns);

    expect(requests).toEqual([]);
    expect(outcome.kind).toBe("landed");
    if (outcome.kind !== "landed") {
      return;
    }
    const serialized = JSON.stringify(outcome.rows.map((row) => submittedVariables(row, columns)));
    expect(serialized).not.toContain("hunter2");
    expect(serialized).not.toContain("password");
    expect(serialized).not.toContain(CONFIDENT_CSV);
    for (const request of requests) {
      expect(request).not.toContain("hunter2");
      expect(request).not.toContain(CONFIDENT_CSV);
    }
  });
});
