import {
  deleteAccount,
  getCurrentAccount,
  signOut,
  signOutEverywhere,
  type Account,
} from "@step-by-step/api-client";
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
  letGo(cache, navigate);
}

/**
 * End every session this account has — this browser's among them — and land
 * here the same way.
 *
 * The two are one action from where the visitor stands, which is why they end
 * identically: what differs is how far the revocation reaches, and that is the
 * instance's business rather than this browser's.
 */
export async function signOutEverywhereAndLeave(
  cache: QueryClient,
  navigate: (to: string) => void,
): Promise<void> {
  await signOutEverywhere();
  letGo(cache, navigate);
}

/**
 * End the account itself, and leave the same way signing out does.
 *
 * The address is passed in rather than read from the identity this browser
 * holds: what confirms the deletion is what the person typed, and a screen
 * that sent the address it already knew would be confirming nothing.
 *
 * A refusal is thrown rather than swallowed — a sole owner has something to do
 * about it, and this browser keeps its session and its identity while they do.
 */
export async function deleteAccountAndLeave(
  cache: QueryClient,
  navigate: (to: string) => void,
  typedEmail: string,
): Promise<void> {
  const { error } = await deleteAccount({ body: { email_confirmation: typedEmail } });
  if (error) {
    throw error;
  }
  letGo(cache, navigate);
}

/** What a browser with no session keeps: nothing, and the sign-in screen. */
function letGo(cache: QueryClient, navigate: (to: string) => void): void {
  cache.clear();
  navigate(SIGN_IN_PATH);
}
