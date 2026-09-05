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
import { followTheme } from "@/lib/theme";

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(createQueryClient);
  const router = useRouter();

  useEffect(followTheme, []);

  useEffect(() => {
    const stops = [
      installOrganizationHeader(() => {
        const me = queryClient.getQueryData<Account | null>(IDENTITY_KEY) ?? null;
        return activeOrganization(me, organizationChoice())?.id ?? null;
      }),

      installUnauthorizedRedirect((to) => {
        queryClient.clear();
        router.replace(to);
      }),

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
