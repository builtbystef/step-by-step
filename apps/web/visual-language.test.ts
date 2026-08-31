import { readdirSync, readFileSync } from "node:fs";
import { extname, join, relative } from "node:path";

import { describe, expect, it } from "vitest";

const WEB_ROOT = import.meta.dirname;
const SKIPPED_DIRECTORIES = new Set(["node_modules", ".next", "dist"]);
const SCANNED_EXTENSIONS = new Set([".ts", ".tsx", ".css"]);

const TOKEN_FILE = "app/globals.css";

// The extension popup cannot import this app's stylesheet, so it declares the
// tokens it needs again. This test is what keeps that copy honest.
const EXTENSION_STYLESHEET = join(WEB_ROOT, "..", "extension", "src", "popup.css");

function declaredTokens(text: string): Map<string, string> {
  const declared = new Map<string, string>();

  for (const [, name, value] of text.matchAll(/^\s*(--[\w-]+):\s*([^;]+);/gm)) {
    if (name !== undefined && value !== undefined) {
      declared.set(name, value.trim());
    }
  }

  return declared;
}

const STATUS_CHIP = "components/primitives/status-chip.tsx";

function sourceFiles(directory: string): string[] {
  const found: string[] = [];

  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (!SKIPPED_DIRECTORIES.has(entry.name)) {
        found.push(...sourceFiles(join(directory, entry.name)));
      }
    } else if (SCANNED_EXTENSIONS.has(extname(entry.name))) {
      found.push(join(directory, entry.name));
    }
  }

  return found;
}

const SOURCES = sourceFiles(WEB_ROOT)
  .map((path) => ({
    path: relative(WEB_ROOT, path).replaceAll("\\", "/"),
    text: readFileSync(path, "utf8"),
  }))
  .filter((source) => !/\.test\.tsx?$/.test(source.path));

describe("the visual language", () => {
  it("scans the frontend it is asserting about", () => {
    expect(SOURCES.length).toBeGreaterThan(15);
    expect(SOURCES.map((source) => source.path)).toContain(TOKEN_FILE);
  });

  it("keeps every raw hex value in the token file", () => {
    const offenders = SOURCES.filter(
      (source) => source.path !== TOKEN_FILE && /#[0-9a-fA-F]{3,8}\b/.test(source.text),
    ).map((source) => source.path);

    expect(offenders).toEqual([]);
  });

  it("gives the extension popup the same value for every token it shares", () => {
    const app = declaredTokens(readFileSync(join(WEB_ROOT, TOKEN_FILE), "utf8"));
    const popup = declaredTokens(readFileSync(EXTENSION_STYLESHEET, "utf8"));

    const shared = [...popup].filter(([name]) => app.has(name));
    const drifted = shared.filter(([name, value]) => app.get(name) !== value);

    expect(shared.map(([name]) => name)).toContain("--accent");
    expect(shared.length).toBeGreaterThan(15);
    expect(drifted).toEqual([]);
  });

  it("renders a lifecycle state only through StatusChip", () => {
    const offenders = SOURCES.filter(
      (source) =>
        source.path !== "lib/labels.ts" &&
        source.path !== STATUS_CHIP &&
        /\b(lifecycleLabel|lifecycleTone)\b/.test(source.text),
    ).map((source) => source.path);

    expect(offenders).toEqual([]);
  });
});
