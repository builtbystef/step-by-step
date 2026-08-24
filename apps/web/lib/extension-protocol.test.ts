import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  CONNECT_ACCEPTED,
  EXTENSION_CHANNEL,
  EXTENSION_PROBE,
  EXTENSION_READY,
  HANDSHAKE,
  RECORDING_FINISHED,
  RECORDING_PENDING,
  RECORDING_PENDING_ACCEPTED,
  RECORDING_TOKEN,
  RECORDING_TOKEN_EXPIRED,
  handshakeMessage,
  readExtensionMessage,
  recordingPendingMessage,
  recordingTokenMessage,
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
    ["RECORDING_PENDING", RECORDING_PENDING],
    ["RECORDING_PENDING_ACCEPTED", RECORDING_PENDING_ACCEPTED],
    ["RECORDING_TOKEN_EXPIRED", RECORDING_TOKEN_EXPIRED],
    ["RECORDING_TOKEN", RECORDING_TOKEN],
    ["RECORDING_FINISHED", RECORDING_FINISHED],
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

  it("reads recording lifecycle messages", () => {
    expect(
      readExtensionMessage({
        channel: EXTENSION_CHANNEL,
        type: RECORDING_TOKEN_EXPIRED,
        sessionId: "session-1",
      }),
    ).toEqual({ type: RECORDING_TOKEN_EXPIRED, version: "", sessionId: "session-1" });
    expect(
      readExtensionMessage({
        channel: EXTENSION_CHANNEL,
        type: RECORDING_FINISHED,
        sessionId: "session-1",
      }),
    ).toEqual({ type: RECORDING_FINISHED, version: "", sessionId: "session-1" });
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
    ["a malformed recording event", { channel: EXTENSION_CHANNEL, type: RECORDING_FINISHED }],
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

describe("recording messages the app hands over", () => {
  it("carries a pending recording without inventing a target tab", () => {
    expect(
      recordingPendingMessage({
        sessionId: "session-1",
        token: "token-1",
        backendOrigin: "https://steps.example.com",
        workflowId: "workflow-1",
        workflowName: "Invoices",
        variables: [{ name: "password", secret: true }],
      }),
    ).toEqual({
      channel: EXTENSION_CHANNEL,
      type: RECORDING_PENDING,
      sessionId: "session-1",
      token: "token-1",
      backendOrigin: "https://steps.example.com",
      workflowId: "workflow-1",
      workflowName: "Invoices",
      mode: "record",
      variables: [{ name: "password", secret: true }],
    });
  });

  it("carries a rotated token for the same session", () => {
    expect(recordingTokenMessage("session-1", "token-2")).toEqual({
      channel: EXTENSION_CHANNEL,
      type: RECORDING_TOKEN,
      sessionId: "session-1",
      token: "token-2",
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
