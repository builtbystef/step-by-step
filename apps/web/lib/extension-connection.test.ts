import { describe, expect, it, vi } from "vitest";

import {
  connectionState,
  probeExtension,
  watchWindowFocus,
  type ProbeWindow,
} from "./extension-connection";
import { EXTENSION_CHANNEL, EXTENSION_PROBE, EXTENSION_READY } from "./extension-protocol";

class FakeWindow extends EventTarget implements ProbeWindow {
  readonly location = { origin: "https://steps.example.com" };
  posted: unknown[] = [];

  postMessage(message: unknown, targetOrigin: string) {
    this.posted.push({ message, targetOrigin });
  }

  message(data: unknown, origin = this.location.origin, source: unknown = this) {
    const event = new Event("message");
    Object.defineProperties(event, {
      data: { value: data },
      origin: { value: origin },
      source: { value: source },
    });
    this.dispatchEvent(event);
  }

  answer(version: string, source: unknown = this) {
    this.message({ channel: EXTENSION_CHANNEL, type: EXTENSION_READY, version }, undefined, source);
  }
}

describe("the extension connection probe", () => {
  it("reports the version announced by the extension", async () => {
    const page = new FakeWindow();
    const result = probeExtension(page, 1_500);

    expect(page.posted).toEqual([
      {
        message: { channel: EXTENSION_CHANNEL, type: EXTENSION_PROBE },
        targetOrigin: "https://steps.example.com",
      },
    ]);

    page.answer("1.2.3");
    await expect(result).resolves.toBe("1.2.3");
  });

  it("treats 1500 ms of silence as not connected", async () => {
    vi.useFakeTimers();
    const page = new FakeWindow();
    const result = probeExtension(page, 1_500);

    await vi.advanceTimersByTimeAsync(1_499);
    let settled = false;
    void result.then(() => {
      settled = true;
    });
    await Promise.resolve();
    expect(settled).toBe(false);

    await vi.advanceTimersByTimeAsync(1);
    await expect(result).resolves.toBeNull();
    vi.useRealTimers();
  });

  it("ignores messages from another window or origin", async () => {
    vi.useFakeTimers();
    const page = new FakeWindow();
    const result = probeExtension(page, 1_500);

    page.answer("9.9.9", {});
    page.message(
      { channel: EXTENSION_CHANNEL, type: EXTENSION_READY, version: "9.9.9" },
      "https://other.example.com",
    );
    await vi.advanceTimersByTimeAsync(1_500);

    await expect(result).resolves.toBeNull();
    vi.useRealTimers();
  });

  it("asks for another probe whenever the window regains focus", () => {
    const page = new FakeWindow();
    const probe = vi.fn();
    const stop = watchWindowFocus(page, probe);

    page.dispatchEvent(new Event("focus"));
    page.dispatchEvent(new Event("focus"));
    expect(probe).toHaveBeenCalledTimes(2);

    stop();
    page.dispatchEvent(new Event("focus"));
    expect(probe).toHaveBeenCalledTimes(2);
  });
});

describe("connection state", () => {
  it.each([
    [null, "1.2.0", "not_connected"],
    ["1.2.0", "1.2.0", "connected"],
    ["1.10.0", "1.2.0", "connected"],
    ["1.1.9", "1.2.0", "out_of_date"],
  ] as const)("maps version %s against minimum %s to %s", (version, minimum, expected) => {
    expect(connectionState(version, minimum)).toBe(expected);
  });
});
