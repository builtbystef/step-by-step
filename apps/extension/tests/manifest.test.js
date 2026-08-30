import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const PACKAGE = join(import.meta.dirname, "..", "src");
const manifest = JSON.parse(readFileSync(join(PACKAGE, "manifest.json"), "utf8"));

describe("the extension package", () => {
  it("is plain MV3, with a service worker that can import a module", () => {
    expect(manifest.manifest_version).toBe(3);
    expect(manifest.background).toEqual({
      service_worker: "service-worker.js",
      type: "module",
    });
  });

  it("pins a key, so the extension id does not follow the install directory", () => {
    const key = Buffer.from(manifest.key, "base64");

    const digest = createHash("sha256").update(key).digest("hex").slice(0, 32);
    const id = [...digest].map((digit) => "abcdefghijklmnop"[parseInt(digit, 16)]).join("");

    expect(id).toMatch(/^[a-p]{32}$/);
    expect(key.length).toBeGreaterThan(160);
  });

  it("declares the Chrome an attached debugger keeps the worker alive on", () => {
    expect(manifest.minimum_chrome_version).toBe("118");
  });

  it("asks for broad host access only as an optional permission", () => {
    expect(manifest.host_permissions).toBeUndefined();
    expect(manifest.optional_host_permissions).toEqual(["*://*/*"]);
    expect(manifest.permissions).toEqual([
      "activeTab",
      "storage",
      "scripting",
      "debugger",
      "webNavigation",
      "downloads",
      "cookies",
    ]);
  });

  it("names only files that are in the package", () => {
    const named = [
      manifest.background.service_worker,
      manifest.action.default_popup,
      "popup.js",
      "popup.css",
      "lib/handshake.js",
      "lib/instance.js",
      "lib/page-bridge.js",
      "recorder-content.js",
    ];

    expect(named.filter((file) => !existsSync(join(PACKAGE, file)))).toEqual([]);
  });
});
