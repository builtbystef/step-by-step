export const PAGE_SIZE = 25;

export const URL_FILTER_KEYS = ["status", "trigger"] as const;

export type CursorPage<T> = {
  items: T[];
  next_cursor?: string | null;
};

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

export function rowsOf<T>(pages: CursorPage<T>[] | undefined): T[] {
  return (pages ?? []).flatMap((page) => page.items);
}
