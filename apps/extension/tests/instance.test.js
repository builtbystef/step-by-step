import { describe, expect, it } from "vitest";

import { originPattern, readInstanceUrl } from "../src/lib/instance.js";

/**
 * What the popup makes of the address a person types. The answer is an origin
 * and nothing else: it is what the permission is asked for, what the content
 * script may be injected into, and what the service worker may fetch — so a
 * path, a query, or a trailing slash must not make two connections out of one
 * instance.
 */

describe("reading an instance address", () => {
  it.each([
    ["https://steps.example.com", "https://steps.example.com"],
    ["https://steps.example.com/", "https://steps.example.com"],
    ["https://steps.example.com/connect?nonce=1", "https://steps.example.com"],
    ["  https://steps.example.com  ", "https://steps.example.com"],
    ["HTTPS://Steps.Example.com", "https://steps.example.com"],
    ["https://steps.example.com:8443", "https://steps.example.com:8443"],
  ])("reads %s as one origin", (typed, origin) => {
    expect(readInstanceUrl(typed)).toEqual({ origin });
  });

  it("assumes https for an address typed without a scheme", () => {
    expect(readInstanceUrl("steps.example.com")).toEqual({ origin: "https://steps.example.com" });
  });

  it("reads a port typed without a scheme as a port, not as a scheme", () => {
    expect(readInstanceUrl("steps.example.com:8443")).toEqual({
      origin: "https://steps.example.com:8443",
    });
  });

  it("keeps http, because a self-hosted instance may be on a private network", () => {
    expect(readInstanceUrl("http://localhost:3000")).toEqual({ origin: "http://localhost:3000" });
  });

  it.each([
    ["", "empty"],
    ["   ", "empty"],
    ["https://", "malformed"],
    ["not a url", "malformed"],
    ["ftp://steps.example.com", "unsupported-scheme"],
    ["javascript:alert(1)", "unsupported-scheme"],
    ["chrome://extensions", "unsupported-scheme"],
  ])("refuses %o", (typed, problem) => {
    expect(readInstanceUrl(typed)).toEqual({ problem });
  });
});

describe("the match pattern an origin asks permission for", () => {
  it("covers the whole origin and nothing beside it", () => {
    expect(originPattern("https://steps.example.com")).toBe("https://steps.example.com/*");
  });
});
