import { QueryClient } from "@tanstack/react-query";

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      // Retrying a mutation could repeat work against a real website.
      mutations: { retry: false },
    },
  });
}
