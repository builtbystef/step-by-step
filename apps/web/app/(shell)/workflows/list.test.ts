import { describe, expect, it } from "vitest";

import { PAGE_SIZE, SEARCH_AND_SORT_FROM, SORT_OPTIONS, offersSearchAndSort } from "./list";

/**
 * The two decisions the Workflows list makes about itself: when it grows a
 * search box and a sort control, and what the sort control offers.
 */

describe("when the list offers a search box and a sort control", () => {
  it("keeps them away until the list is long enough to need them", () => {
    expect(offersSearchAndSort(0, false)).toBe(false);
    expect(offersSearchAndSort(SEARCH_AND_SORT_FROM - 1, false)).toBe(false);
    expect(offersSearchAndSort(SEARCH_AND_SORT_FROM, false)).toBe(true);
  });

  it("asks for a page exactly as long as the threshold, so one page decides", () => {
    expect(PAGE_SIZE).toBe(SEARCH_AND_SORT_FROM);
  });

  it("keeps them while a search is on, whatever the search left behind", () => {
    expect(offersSearchAndSort(1, true)).toBe(true);
    expect(offersSearchAndSort(0, true)).toBe(true);
  });
});

describe("the sort control", () => {
  it("offers the three orders the endpoint has, activity first", () => {
    expect(SORT_OPTIONS.map((option) => option.value)).toEqual(["activity", "name", "created"]);
  });

  it("labels each of them differently, in words rather than in field names", () => {
    const labels = SORT_OPTIONS.map((option) => option.label);

    expect(new Set(labels).size).toBe(SORT_OPTIONS.length);
    expect(labels).not.toContain("activity");
  });
});
