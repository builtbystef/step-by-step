import { describe, expect, it } from "vitest";

import { duration } from "./duration";

describe("a length of time, written out", () => {
  it("keeps milliseconds below a second, where seconds would round to nothing", () => {
    expect(duration(800)).toBe("800 ms");
    expect(duration(1)).toBe("1 ms");
  });

  it("reads a round number of seconds as seconds", () => {
    expect(duration(1000)).toBe("1 s");
    expect(duration(5000)).toBe("5 s");
    expect(duration(30_000)).toBe("30 s");
  });

  it("keeps one decimal when the seconds are not round, and drops it when they are", () => {
    expect(duration(1500)).toBe("1.5 s");
    expect(duration(2250)).toBe("2.3 s");
  });

  it("breaks a minute or more into minutes and seconds", () => {
    expect(duration(60_000)).toBe("1 min");
    expect(duration(90_000)).toBe("1 min 30 s");
    expect(duration(30 * 60_000)).toBe("30 min");
  });
});
