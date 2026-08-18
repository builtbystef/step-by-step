import { getCurrentAccount, signOut, type Account } from "@step-by-step/api-client";
import type { QueryClient } from "@tanstack/react-query";

import { SIGN_IN_PATH } from "./gate";

/**
 * Who the visitor is: one query key, so that every screen that needs the
 * answer shares the one request, and one way to give it up.
 */

/** The key the identity lives under. Invalidate it; never fetch around it. */
export const IDENTITY_KEY = ["identity"] as const;

/**
 * The identity as a query, for `useQuery`.
 *
 * `retry: false` because a 401 is an answer, not a failure to reach anyone —
 * retrying it would only delay the redirect the wrapper is about to make. The
 * minute of `staleTime` is a backstop: signing in, signing out, and switching
 * Organization each invalidate this key, so nothing waits on the clock.
 */
export function identityQuery() {
  return {
    queryKey: IDENTITY_KEY,
    retry: false,
    staleTime: 60_000,
    queryFn: async (): Promise<Account | null> => (await getCurrentAccount()).data ?? null,
  };
}

/**
 * End the session, forget who this was, and land on sign-in.
 *
 * Nothing is carried: `next` says "you were sent away from somewhere", and
 * someone who signed out was not sent anywhere. The cache is emptied rather
 * than the one key removed, because everything in it was read as this person.
 */
export async function signOutAndLeave(
  cache: QueryClient,
  navigate: (to: string) => void,
): Promise<void> {
  // The answer is a value, not an exception: a session that had already ended
  // leaves the same visitor in the same place as one that ended just now.
  await signOut();
  cache.clear();
  navigate(SIGN_IN_PATH);
}
