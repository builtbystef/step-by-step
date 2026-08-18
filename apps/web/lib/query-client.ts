import { QueryClient } from "@tanstack/react-query";

/**
 * The app's one QueryClient.
 *
 * Two defaults are mandated rather than inherited from the library:
 *
 * - `mutations.retry: false`. A retried `POST /api/workflows/{id}/runs` or
 *   `POST /api/schedules/{id}/run-now` is a second Run acting on a real
 *   website — the hazard the "two copies never act at once" invariant exists
 *   to prevent, and the one place ADR 0002's spirit reaches the HTTP layer.
 * - No query `retry` and no query `staleTime` here on purpose. Each key
 *   chooses its own: the attention poll and a Workflows list have nothing in
 *   common, and an inherited default would be a decision nobody made.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      mutations: { retry: false },
    },
  });
}
