import { describe, expect, it } from "vitest";

import { codeLifetime, codeRefusal, connectDetail, connectHeadline } from "./messages";

describe("what the connect screen says", () => {
  it("tells the three states apart", () => {
    const said = [
      connectHeadline({ kind: "waiting" }),
      connectHeadline({ kind: "connected", version: "0.1.0" }),
      connectHeadline({ kind: "opened-by-hand" }),
    ];

    expect(new Set(said).size).toBe(3);
    expect(said.every((line) => line.length > 0)).toBe(true);
  });

  it("asks for nothing once the connection is made", () => {
    expect(connectDetail({ kind: "connected", version: "0.1.0" })).toContain("close this tab");
  });

  it("says where the extension is, for someone who opened this page themselves", () => {
    expect(connectDetail({ kind: "opened-by-hand" })).toContain("toolbar");
  });
});

describe("a refused connect code", () => {
  it("reads the machine-readable code, never the prose", () => {
    expect(codeRefusal({ code: "bad_code", message: "whatever the backend said" })).toContain(
      "no longer valid",
    );
  });

  it("has something to say about anything else", () => {
    expect(codeRefusal(undefined)).toContain("Try again");
    expect(codeRefusal({ code: "unheard_of" })).toContain("Try again");
  });
});

describe("how long a code has left", () => {
  const now = new Date("2026-08-18T12:00:00Z");

  it("counts whole minutes", () => {
    expect(codeLifetime("2026-08-18T12:10:00Z", now)).toContain("the next 10 minutes");
  });

  it("says the last minute in the singular", () => {
    expect(codeLifetime("2026-08-18T12:01:00Z", now)).toContain("one more minute");
  });

  it("says so once it has run out", () => {
    expect(codeLifetime("2026-08-18T11:59:00Z", now)).toContain("expired");
    expect(codeLifetime("not a date", now)).toContain("expired");
  });
});
