import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  CONNECT_ACCEPTED,
  EXTENSION_CHANNEL,
  EXTENSION_PROBE,
  EXTENSION_READY,
  HANDSHAKE,
  handshakeMessage,
  readExtensionMessage,
} from "./extension-protocol";

/**
 * One end of a conversation, checked against the other. The extension is a
 * package of its own with no build step and nothing importable from here, so
 * what keeps the two ends speaking the same protocol is this file.
 */

const EXTENSION_SOURCE = readFileSync(
  join(import.meta.dirname, "..", "..", "extension", "src", "lib", "handshake.js"),
  "utf8",
);

describe("the protocol's names", () => {
  it.each([
    ["CHANNEL", EXTENSION_CHANNEL],
    ["HANDSHAKE", HANDSHAKE],
    ["PROBE", EXTENSION_PROBE],
    ["READY", EXTENSION_READY],
    ["ACCEPTED", CONNECT_ACCEPTED],
  ])("is the extension's own %s", (name, value) => {
    expect(EXTENSION_SOURCE).toContain(`export const ${name} = "${value}";`);
  });
});

describe("reading what the extension says", () => {
  it("reads a bridge that has arrived, with its version", () => {
    expect(
      readExtensionMessage({ channel: EXTENSION_CHANNEL, type: EXTENSION_READY, version: "0.1.0" }),
    ).toEqual({ type: EXTENSION_READY, version: "0.1.0" });
  });

  it("reads an accepted connection", () => {
    expect(
      readExtensionMessage({
        channel: EXTENSION_CHANNEL,
        type: CONNECT_ACCEPTED,
        version: "0.1.0",
      }),
    ).toEqual({ type: CONNECT_ACCEPTED, version: "0.1.0" });
  });

  it.each([
    ["nothing", null],
    ["a string", "connected"],
    ["another channel", { channel: "other", type: CONNECT_ACCEPTED }],
    ["another type", { channel: EXTENSION_CHANNEL, type: "recording-started" }],
    ["the handshake this page itself posted", { channel: EXTENSION_CHANNEL, type: HANDSHAKE }],
  ])("ignores %s", (_what, data) => {
    expect(readExtensionMessage(data)).toBeNull();
  });

  it("survives a message with no version, because the screen still has state to show", () => {
    expect(readExtensionMessage({ channel: EXTENSION_CHANNEL, type: CONNECT_ACCEPTED })).toEqual({
      type: CONNECT_ACCEPTED,
      version: "",
    });
  });
});

describe("the handshake this page hands over", () => {
  it("carries the nonce and the origin it is served from", () => {
    expect(handshakeMessage("f2b1", "https://steps.example.com")).toEqual({
      channel: EXTENSION_CHANNEL,
      type: HANDSHAKE,
      nonce: "f2b1",
      instanceOrigin: "https://steps.example.com",
    });
  });
});
