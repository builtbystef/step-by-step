import { describe, expect, it } from "vitest";

import { deleteConsequence, usedBySummary } from "./usage";

describe("how Settings names the Workflows that bind to a Secret", () => {
  it("says used by N workflows and lists the names", () => {
    expect(usedBySummary([])).toBe("used by 0 workflows");
    expect(usedBySummary([{ workflow_name: "Invoices" }])).toBe("used by 1 workflow · Invoices");
    expect(usedBySummary([{ workflow_name: "Invoices" }, { workflow_name: "Payroll" }])).toBe(
      "used by 2 workflows · Invoices, Payroll",
    );
  });

  it("names the referencing Workflows in the delete confirmation, then proceeds anyway", () => {
    expect(deleteConsequence("acme-portal-password", [])).toContain("No Workflow uses it");
    expect(deleteConsequence("acme-portal-password", [{ workflow_name: "Invoices" }])).toContain(
      "Invoices",
    );
    expect(
      deleteConsequence("acme-portal-password", [
        { workflow_name: "Invoices" },
        { workflow_name: "Payroll" },
      ]),
    ).toMatch(/Invoices.*Payroll/);
  });
});
