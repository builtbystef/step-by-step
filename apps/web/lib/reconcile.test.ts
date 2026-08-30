import { describe, expect, it } from "vitest";

import { reconcile, type ReconcileVariable } from "./reconcile";

const CITY: ReconcileVariable = { name: "city" };
const ZIP_CODE: ReconcileVariable = { name: "zipCode" };
const PASSWORD: ReconcileVariable = { name: "password", secret: true };

describe("reconcile", () => {
  it("matches City and zip_code, ignores notes, and is confident", () => {
    const result = reconcile(["City", "zip_code", "notes"], [CITY, ZIP_CODE]);

    expect(result.confident).toBe(true);
    expect(result.ignoredHeaders).toEqual(["notes"]);
    expect(result.mapping).toEqual([
      { variableName: "city", header: "City", suggested: false },
      { variableName: "zipCode", header: "zip_code", suggested: false },
    ]);
    expect(result.droppedSecretHeaders).toEqual([]);
  });

  it("offers cite → city and zip → zipCode as unapplied suggestions", () => {
    const result = reconcile(["cite", "zip"], [CITY, ZIP_CODE]);

    expect(result.confident).toBe(false);
    expect(result.mapping).toEqual([
      { variableName: "city", header: "cite", suggested: true },
      { variableName: "zipCode", header: "zip", suggested: true },
    ]);
  });

  it("drops a secret Variable's column and still covers the rest", () => {
    const result = reconcile(["city", "password"], [CITY, PASSWORD]);

    expect(result.confident).toBe(true);
    expect(result.droppedSecretHeaders).toEqual(["password"]);
    expect(result.mapping).toEqual([{ variableName: "city", header: "city", suggested: false }]);
  });

  it("is not confident when two headers claim one Variable", () => {
    const result = reconcile(["city", "City"], [CITY]);

    expect(result.confident).toBe(false);
    expect(result.mapping).toEqual([{ variableName: "city", header: null, suggested: false }]);
  });
});
