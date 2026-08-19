import { describe, expect, it } from "vitest";

import {
  CHANNEL,
  HANDSHAKE,
  judgeHandshake,
  mintNonce,
  readHandshake,
} from "../src/lib/handshake.js";

/**
 * The rule every message the extension accepts is held to. A page can say
 * anything to a content script, and any tab can talk to the service worker, so
 * the connect handshake is accepted only from the tab this attempt opened, at
 * the origin this attempt asked permission for, carrying the nonce this
 * attempt minted.
 */

const ORIGIN = "https://steps.example.com";
const NONCE = "b8f0f0f8d9e64a1a9c2d3e4f50617283b8f0f0f8d9e64a1a9c2d3e4f50617283";
const EXTENSION_ID = "abcdefghijklmnopabcdefghijklmnop";

const attempt = { origin: ORIGIN, nonce: NONCE, tabId: 7 };

function handshake(overrides = {}) {
  return { channel: CHANNEL, type: HANDSHAKE, nonce: NONCE, instanceOrigin: ORIGIN, ...overrides };
}

function sender(overrides = {}) {
  return {
    id: EXTENSION_ID,
    origin: ORIGIN,
    url: `${ORIGIN}/connect`,
    frameId: 0,
    tab: { id: 7 },
    ...overrides,
  };
}

function judge(overrides = {}) {
  return judgeHandshake({
    message: handshake(),
    sender: sender(),
    attempt,
    extensionId: EXTENSION_ID,
    ...overrides,
  });
}

describe("reading a handshake", () => {
  it("reads the nonce and the origin the page claims", () => {
    expect(readHandshake(handshake())).toEqual({ nonce: NONCE, instanceOrigin: ORIGIN });
  });

  it.each([
    ["nothing at all", null],
    ["a string", "connect"],
    ["another channel's message", { channel: "other", type: HANDSHAKE, nonce: NONCE }],
    ["another type", { channel: CHANNEL, type: "connect-accepted", nonce: NONCE }],
    ["no nonce", { channel: CHANNEL, type: HANDSHAKE, instanceOrigin: ORIGIN }],
    ["a nonce that is not a string", handshake({ nonce: 12 })],
    ["an origin that is not a string", handshake({ instanceOrigin: null })],
  ])("refuses %s", (_what, data) => {
    expect(readHandshake(data)).toBeNull();
  });
});

describe("judging a handshake", () => {
  it("accepts the tab this attempt opened, with this attempt's nonce", () => {
    expect(judge()).toEqual({ accepted: true, origin: ORIGIN });
  });

  it("refuses a message when no connect attempt is outstanding", () => {
    expect(judge({ attempt: null })).toEqual({ accepted: false, reason: "no-attempt" });
  });

  it("refuses a sender that is not this extension", () => {
    expect(judge({ sender: sender({ id: "ponmlkjihgfedcbaponmlkjihgfedcba" }) })).toEqual({
      accepted: false,
      reason: "not-our-sender",
    });
  });

  it("refuses a message that came from no tab at all", () => {
    expect(judge({ sender: sender({ tab: undefined }) })).toEqual({
      accepted: false,
      reason: "not-a-tab",
    });
  });

  it("refuses a frame inside the page", () => {
    expect(judge({ sender: sender({ frameId: 3 }) })).toEqual({
      accepted: false,
      reason: "not-the-top-frame",
    });
  });

  it("refuses a tab this attempt did not open", () => {
    expect(judge({ sender: sender({ tab: { id: 9 } }) })).toEqual({
      accepted: false,
      reason: "not-the-connected-tab",
    });
  });

  it("refuses a sender at another origin", () => {
    expect(judge({ sender: sender({ origin: "https://elsewhere.example.com" }) })).toEqual({
      accepted: false,
      reason: "wrong-origin",
    });
  });

  it("refuses a page that claims an origin it is not served from", () => {
    expect(
      judge({ message: handshake({ instanceOrigin: "https://elsewhere.example.com" }) }),
    ).toEqual({ accepted: false, reason: "wrong-origin" });
  });

  it("refuses a payload that is not a handshake", () => {
    expect(judge({ message: { channel: CHANNEL, type: "something-else" } })).toEqual({
      accepted: false,
      reason: "malformed",
    });
  });

  it("refuses a nonce this attempt did not mint", () => {
    expect(judge({ message: handshake({ nonce: mintNonce() }) })).toEqual({
      accepted: false,
      reason: "wrong-nonce",
    });
  });

  it("refuses a nonce that is merely a prefix of this attempt's", () => {
    expect(judge({ message: handshake({ nonce: NONCE.slice(0, 16) }) })).toEqual({
      accepted: false,
      reason: "wrong-nonce",
    });
  });
});

describe("minting a nonce", () => {
  it("is 256 bits of hex", () => {
    expect(mintNonce()).toMatch(/^[0-9a-f]{64}$/);
  });

  it("is never the same twice", () => {
    const minted = new Set(Array.from({ length: 50 }, () => mintNonce()));

    expect(minted.size).toBe(50);
  });
});
