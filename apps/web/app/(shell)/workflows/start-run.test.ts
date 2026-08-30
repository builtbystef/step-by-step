import { describe, expect, it } from "vitest";

import type { Variable } from "@step-by-step/api-client";

import { columnsOf, emptyRow, submittedVariables } from "../../../components/value-grid/grid";

import { needsValueGrid, startBody } from "./start-run";

const PLAIN: Variable = { name: "customer", secret: false };
const SECRET: Variable = { name: "password", secret: true, secretName: "vault-password" };

describe("whether starting opens the value grid", () => {
  it("starts immediately when the Workflow declares no Variables", () => {
    expect(needsValueGrid([])).toBe(false);
  });

  it("opens the grid when it declares any, including only secrets", () => {
    expect(needsValueGrid([PLAIN])).toBe(true);
    expect(needsValueGrid([SECRET])).toBe(true);
    expect(needsValueGrid([PLAIN, SECRET])).toBe(true);
  });
});

describe("the start payload", () => {
  it("sends the typed values and nothing for a secret Variable", () => {
    const columns = columnsOf([PLAIN, SECRET]);
    const row = { ...emptyRow(columns), customer: "Ada" };

    expect(startBody(row, columns)).toEqual({ variables: { customer: "Ada" } });
    expect(submittedVariables(row, columns)).not.toHaveProperty("password");
  });
});
