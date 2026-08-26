/**
 * The shared cursor-list: page size, the query key mutations invalidate, and
 * mirroring filters into the URL so a filtered list is linkable and survives
 * a reload.
 *
 * Both the Runs list and the Schedules list sit on this. The hook is a thin
 * wrapper over TanStack Query's `useInfiniteQuery`; these are the decisions
 * it makes before it draws anything.
 */

/** How many rows a page asks for. The hook owns this, not each list. */
export const PAGE_SIZE = 25;

/**
 * Filters that belong in the address. A Workflow id is a route, not a
 * filter: putting it in the query would duplicate the path the tab already
 * names.
 */
export const URL_FILTER_KEYS = ["status", "trigger"] as const;

export type CursorPage<T> = {
  items: T[];
  next_cursor?: string | null;
};

/**
 * The key a mutation invalidates by prefix. `orgId` is in it so switching
 * Organizations cannot serve the previous tenant's page; `filters` so a
 * filtered list is its own cache entry.
 */
export function cursorListKey(path: string, orgId: string, filters: Record<string, string>) {
  return [path, orgId, filters] as const;
}

export function filtersFromSearch(
  search: Pick<URLSearchParams, "get">,
  keys: readonly string[] = URL_FILTER_KEYS,
): Record<string, string> {
  const filters: Record<string, string> = {};
  for (const key of keys) {
    const value = search.get(key);
    if (value !== null && value !== "") {
      filters[key] = value;
    }
  }
  return filters;
}

/**
 * The query string with the mirrored keys rewritten and every other param
 * left alone — a Version being read, a `next` from sign-in, anything the
 * list does not own.
 */
export function withMirroredFilters(
  current: URLSearchParams,
  filters: Record<string, string>,
  keys: readonly string[] = URL_FILTER_KEYS,
): string {
  const next = new URLSearchParams(current.toString());
  for (const key of keys) {
    next.delete(key);
    const value = filters[key];
    if (value !== undefined && value !== "") {
      next.set(key, value);
    }
  }
  const encoded = next.toString();
  return encoded === "" ? "" : `?${encoded}`;
}

/** Every row loaded so far, flattened out of the pages that carried them. */
export function rowsOf<T>(pages: CursorPage<T>[] | undefined): T[] {
  return (pages ?? []).flatMap((page) => page.items);
}
