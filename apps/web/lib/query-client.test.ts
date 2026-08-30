import { describe, expect, it } from "vitest";

import { createQueryClient } from "./query-client";

describe("the query client", () => {
  it("never retries a mutation", () => {
    expect(createQueryClient().getDefaultOptions().mutations?.retry).toBe(false);
  });

  it("leaves query retry and staleTime to each key", () => {
    const queries = createQueryClient().getDefaultOptions().queries;
    expect(queries?.retry).toBeUndefined();
    expect(queries?.staleTime).toBeUndefined();
  });
});
