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

// A stylesheet states its light palette first and its dark palette after one of
// these markers, so the two can be compared theme by theme.
const DARK_MARKER = /^\s*(?:\.dark\s*\{|@media \(prefers-color-scheme: dark\))/m;

function palettes(text: string): { light: Map<string, string>; dark: Map<string, string> } {
  const at = text.search(DARK_MARKER);
  if (at < 0) {
    return { light: declaredTokens(text), dark: new Map() };
  }
  return { light: declaredTokens(text.slice(0, at)), dark: declaredTokens(text.slice(at)) };
}

// The brand hues are the logo's, and a logo does not change with the theme.
function colourNames(tokens: Map<string, string>): string[] {
  return [...tokens]
    .filter(([name, value]) => value.startsWith("#") && !name.startsWith("--brand-"))
    .map(([name]) => name);
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

  it("gives every colour a dark value under the same name", () => {
    const app = palettes(readFileSync(join(WEB_ROOT, TOKEN_FILE), "utf8"));

    expect(colourNames(app.light)).toContain("--accent");
    expect(colourNames(app.dark).toSorted()).toEqual(colourNames(app.light).toSorted());
  });

  it("gives the extension popup the same value for every token it shares", () => {
    const app = palettes(readFileSync(join(WEB_ROOT, TOKEN_FILE), "utf8"));
    const popup = palettes(readFileSync(EXTENSION_STYLESHEET, "utf8"));

    for (const theme of ["light", "dark"] as const) {
      const shared = [...popup[theme]].filter(([name]) => app[theme].has(name));
      const drifted = shared.filter(([name, value]) => app[theme].get(name) !== value);

      expect(shared.map(([name]) => name)).toContain("--accent");
      expect(shared.length).toBeGreaterThan(15);
      expect(drifted).toEqual([]);
    }
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
