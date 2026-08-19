"use client";

import type { Account } from "@step-by-step/api-client";
import { QueryClientProvider } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { activeOrganization, chooseOrganization, organizationChoice } from "@/lib/active-org";
import {
  installMembershipLapsed,
  installOrganizationHeader,
  installUnauthorizedRedirect,
} from "@/lib/api";
import { IDENTITY_KEY } from "@/lib/identity";
import { createQueryClient } from "@/lib/query-client";

export function Providers({ children }: { children: ReactNode }) {
  // One client per browser session, created once rather than on every render.
  const [queryClient] = useState(createQueryClient);
  const router = useRouter();

  // The wrapper's three rules, installed once for the whole app: every
  // generated call goes through the one client, so this is the only place any
  // of them has to be said.
  useEffect(() => {
    const stops = [
      // The acting Organization, derived at the call rather than held beside
      // the cache: the identity says which Memberships are real and the
      // choice says which of them is active, so there is no third copy to
      // fall out of step with either.
      installOrganizationHeader(() => {
        const me = queryClient.getQueryData<Account | null>(IDENTITY_KEY) ?? null;
        return activeOrganization(me, organizationChoice())?.id ?? null;
      }),

      // What was read as the old session is given up before the redirect, and
      // that order matters: a cached identity would tell the sign-in screen
      // that this visitor is signed in, and it would send them straight back
      // to the screen that just answered 401.
      installUnauthorizedRedirect((to) => {
        queryClient.clear();
        router.replace(to);
      }),

      // A Membership that ended mid-tab: the choice it named is given up and
      // everything read through it is re-read, which turns a tab full of
      // refusals back into a working one without a reload.
      installMembershipLapsed(() => {
        chooseOrganization(null);
        void queryClient.invalidateQueries();
      }),
    ];

    return () => {
      for (const stop of stops) {
        stop();
      }
    };
  }, [queryClient, router]);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
