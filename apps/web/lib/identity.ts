import {
  deleteAccount,
  getCurrentAccount,
  signOut,
  signOutEverywhere,
  type Account,
} from "@step-by-step/api-client";
import type { QueryClient } from "@tanstack/react-query";

import { SIGN_IN_PATH } from "./gate";

export const IDENTITY_KEY = ["identity"] as const;

export function identityQuery() {
  return {
    queryKey: IDENTITY_KEY,
    retry: false,
    staleTime: 60_000,
    queryFn: async (): Promise<Account | null> => (await getCurrentAccount()).data ?? null,
  };
}

export async function signOutAndLeave(
  cache: QueryClient,
  navigate: (to: string) => void,
): Promise<void> {
  await signOut();
  letGo(cache, navigate);
}

export async function signOutEverywhereAndLeave(
  cache: QueryClient,
  navigate: (to: string) => void,
): Promise<void> {
  await signOutEverywhere();
  letGo(cache, navigate);
}

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

function letGo(cache: QueryClient, navigate: (to: string) => void): void {
  cache.clear();
  navigate(SIGN_IN_PATH);
}
