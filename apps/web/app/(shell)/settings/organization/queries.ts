import { listMembers } from "@step-by-step/api-client";

export function membersKey(orgId: string) {
  return ["members", orgId] as const;
}

export function membersQuery(orgId: string) {
  return {
    queryKey: membersKey(orgId),
    queryFn: async () => (await listMembers({ path: { org_id: orgId } })).data ?? [],
  };
}
