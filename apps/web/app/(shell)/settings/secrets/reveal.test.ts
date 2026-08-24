import { describe, expect, it } from "vitest";

import { REVEAL_DURATION_MS } from "./reveal";

describe("Secret reveal courtesy", () => {
  it("re-masks a revealed value after thirty seconds", () => {
    expect(REVEAL_DURATION_MS).toBe(30_000);
  });
});
