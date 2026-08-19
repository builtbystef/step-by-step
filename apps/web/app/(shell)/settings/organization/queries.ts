import { listMembers } from "@step-by-step/api-client";

/**
 * Who is in the active Organization — one key, because two sections read it:
 * Members renders the list, and General offers the owner somebody to hand the
 * Organization to. A removal in one is a shorter list in the other.
 */
export function membersKey(orgId: string) {
  return ["members", orgId] as const;
}

export function membersQuery(orgId: string) {
  return {
    queryKey: membersKey(orgId),
    queryFn: async () => (await listMembers({ path: { org_id: orgId } })).data ?? [],
  };
}
