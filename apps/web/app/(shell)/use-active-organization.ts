"use client";

import type { Account, OrganizationMembership } from "@step-by-step/api-client";
import { useQuery } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";

import { activeOrganization, organizationChoice, watchOrganizationChoice } from "@/lib/active-org";
import { identityQuery } from "@/lib/identity";

export function useActiveOrganization(): {
  me: Account | null;
  active: OrganizationMembership | null;
} {
  const identity = useQuery(identityQuery());
  const me = identity.data ?? null;

  const choice = useSyncExternalStore(
    watchOrganizationChoice,
    () => organizationChoice(),
    () => null,
  );

  return { me, active: activeOrganization(me, choice) };
}
