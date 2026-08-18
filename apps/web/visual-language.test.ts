import { readdirSync, readFileSync } from "node:fs";
import { extname, join, relative } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * The two rules the visual language is reviewed against, asserted over the
 * frontend's own source so that a later slice cannot quietly break them.
 */

const WEB_ROOT = import.meta.dirname;
const SKIPPED_DIRECTORIES = new Set(["node_modules", ".next", "dist"]);
const SCANNED_EXTENSIONS = new Set([".ts", ".tsx", ".css"]);

/** The one file allowed to name a colour, because it is where colours are defined. */
const TOKEN_FILE = "app/globals.css";

/** The one component allowed to render a lifecycle state. */
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

// The tests themselves are excluded: this file names both rules in order to
// check them, and `lib/labels.test.ts` exercises the wording directly.
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
