import { describe, expect, it } from "vitest";

import { createQueryClient } from "./query-client";

describe("the query client", () => {
  it("never retries a mutation", () => {
    // A retried POST /api/workflows/{id}/runs is a second Run acting on a real
    // website. This default is the one place ADR 0002's spirit reaches HTTP.
    expect(createQueryClient().getDefaultOptions().mutations?.retry).toBe(false);
  });

  it("leaves query retry and staleTime to each key", () => {
    const queries = createQueryClient().getDefaultOptions().queries;
    expect(queries?.retry).toBeUndefined();
    expect(queries?.staleTime).toBeUndefined();
  });
});
