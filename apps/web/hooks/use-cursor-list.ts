"use client";

import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import {
  PAGE_SIZE,
  URL_FILTER_KEYS,
  cursorListKey,
  rowsOf,
  withMirroredFilters,
  type CursorPage,
} from "@/lib/cursor-list";

/**
 * The shared infinite-query wrapper both lists sit on.
 *
 * It owns page size, Load more, and mirroring filter state into the URL.
 * It does not poll and it does not refetch on focus: a list refreshes on
 * navigation, on filter change, and on Load more.
 */

export function useCursorList<T>({
  path,
  orgId,
  filters,
  fetchPage,
  urlKeys = URL_FILTER_KEYS,
}: {
  path: string;
  orgId: string;
  filters: Record<string, string>;
  fetchPage: (args: { cursor: string | null; limit: number }) => Promise<CursorPage<T>>;
  urlKeys?: readonly string[];
}): {
  items: T[];
  loading: boolean;
  hasMore: boolean;
  fetchingMore: boolean;
  error: unknown;
  loadMore: () => void;
  refresh: () => void;
  setFilter: (key: string, value: string) => void;
} {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const cache = useQueryClient();

  const list = useInfiniteQuery({
    queryKey: cursorListKey(path, orgId, filters),
    queryFn: async ({ pageParam }: { pageParam: string | null }): Promise<CursorPage<T>> =>
      fetchPage({ cursor: pageParam, limit: PAGE_SIZE }),
    initialPageParam: null as string | null,
    getNextPageParam: (last: CursorPage<T>): string | null => last.next_cursor ?? null,
    refetchOnWindowFocus: false,
  });

  const setFilter = (key: string, value: string) => {
    const next = { ...filters };
    if (value === "") {
      delete next[key];
    } else {
      next[key] = value;
    }
    const query = withMirroredFilters(new URLSearchParams(searchParams.toString()), next, urlKeys);
    router.replace(`${pathname}${query}`, { scroll: false });
  };

  return {
    items: rowsOf(list.data?.pages),
    loading: list.isPending,
    hasMore: Boolean(list.hasNextPage),
    fetchingMore: list.isFetchingNextPage,
    error: list.error,
    loadMore: () => {
      void list.fetchNextPage();
    },
    refresh: () => {
      void cache.invalidateQueries({ queryKey: cursorListKey(path, orgId, filters) });
    },
    setFilter,
  };
}
