"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { installUnauthorizedRedirect } from "@/lib/api";
import { createQueryClient } from "@/lib/query-client";

export function Providers({ children }: { children: ReactNode }) {
  // One client per browser session, created once rather than on every render.
  const [queryClient] = useState(createQueryClient);
  const router = useRouter();

  // The 401 rule, installed once for the whole app: every generated call goes
  // through the one client, so this is the only place it has to be said.
  //
  // What was read as the old session is given up before the redirect, and that
  // order matters: a cached identity would tell the sign-in screen that this
  // visitor is signed in, and it would send them straight back to the screen
  // that just answered 401.
  useEffect(
    () =>
      installUnauthorizedRedirect((to) => {
        queryClient.clear();
        router.replace(to);
      }),
    [queryClient, router],
  );

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
