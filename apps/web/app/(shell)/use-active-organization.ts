"use client";

import type { Account, OrganizationMembership } from "@step-by-step/api-client";
import { useQuery } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";

import { activeOrganization, organizationChoice, watchOrganizationChoice } from "@/lib/active-org";
import { identityQuery } from "@/lib/identity";

/**
 * Who the visitor is and which Organization they are acting in — the two facts
 * every screen inside the shell reads, from the one identity query they all
 * share and the one choice the switcher makes.
 *
 * The choice is watched rather than passed down: switching has to re-scope
 * every screen at once, and a value threaded through props would re-scope
 * whichever of them happened to re-render.
 */
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
