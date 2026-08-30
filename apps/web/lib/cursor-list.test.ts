import { describe, expect, it } from "vitest";

import {
  PAGE_SIZE,
  URL_FILTER_KEYS,
  cursorListKey,
  filtersFromSearch,
  rowsOf,
  withMirroredFilters,
} from "./cursor-list";

describe("the cursor-list page", () => {
  it("owns one page size for every list that sits on it", () => {
    expect(PAGE_SIZE).toBe(25);
  });
});

describe("the cursor-list query key", () => {
  it("starts with the path, so a prefix invalidation reaches every filter", () => {
    const key = cursorListKey("/api/runs", "org-1", { status: "failed" });

    expect(key[0]).toBe("/api/runs");
    expect(key).toEqual(["/api/runs", "org-1", { status: "failed" }]);
  });

  it("treats a scoped list as a different cache entry from the global one", () => {
    const global = cursorListKey("/api/runs", "org-1", { status: "failed" });
    const scoped = cursorListKey("/api/runs", "org-1", {
      status: "failed",
      workflow_id: "wf-1",
    });

    expect(global).not.toEqual(scoped);
  });
});

describe("mirroring filters into the URL", () => {
  it("reads only the mirrored keys, dropping blanks", () => {
    const search = new URLSearchParams("status=failed&trigger=manual&other=keep");

    expect(filtersFromSearch(search)).toEqual({ status: "failed", trigger: "manual" });
    expect(filtersFromSearch(new URLSearchParams("status=&trigger=batch"))).toEqual({
      trigger: "batch",
    });
  });

  it("writes only the mirrored keys and leaves the rest of the query alone", () => {
    const current = new URLSearchParams("version=2&status=queued");

    expect(withMirroredFilters(current, { status: "failed", trigger: "test" })).toBe(
      "?version=2&status=failed&trigger=test",
    );
  });

  it("drops a cleared filter so an unfiltered list has a clean address", () => {
    const current = new URLSearchParams("status=failed&trigger=manual");

    expect(withMirroredFilters(current, {})).toBe("");
    expect(withMirroredFilters(current, { status: "failed" })).toBe("?status=failed");
  });

  it("mirrors status and trigger, never the Workflow the route already names", () => {
    expect(URL_FILTER_KEYS).toEqual(["status", "trigger"]);
  });
});

describe("flattening pages", () => {
  it("is the rows loaded so far, in the order the pages arrived", () => {
    expect(rowsOf(undefined)).toEqual([]);
    expect(rowsOf([{ items: [1, 2] }, { items: [3] }])).toEqual([1, 2, 3]);
  });
});
