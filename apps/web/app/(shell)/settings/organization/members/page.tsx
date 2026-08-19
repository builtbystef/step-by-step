"use client";

import {
  changeMemberRole,
  removeMember,
  type AssignableRole,
  type Member,
  type OrganizationMembership,
} from "@step-by-step/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { memberControls, memberLabel, refusalMessage } from "../messages";
import { membersKey, membersQuery } from "../queries";

import { useActiveOrganization } from "../../../use-active-organization";

import { AttributeBadge } from "@/components/primitives/attribute-badge";
import { Callout } from "@/components/primitives/callout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { IDENTITY_KEY } from "@/lib/identity";

/**
 * Settings → Organization → Members: everybody in the active Organization.
 *
 * Every role reads the list — who is in a team is not a secret from it. Only
 * an owner and an admin change a role or end a Membership, and the row a
 * person is looking at is their own way out.
 */
export default function MembersPage() {
  const { me, active } = useActiveOrganization();

  if (me === null || active === null) {
    return null;
  }

  return <MemberList org={active} viewerId={me.id} />;
}

function MemberList({ org, viewerId }: { org: OrganizationMembership; viewerId: string }) {
  const cache = useQueryClient();
  const members = useQuery(membersQuery(org.id));

  /**
   * Both keys, always. A role and a removal each change what the identity says
   * about this visitor — which Organizations they are in and what they may do
   * there — and the screen reads its own place from it.
   */
  const refresh = async () => {
    await Promise.all([
      cache.invalidateQueries({ queryKey: membersKey(org.id) }),
      cache.invalidateQueries({ queryKey: IDENTITY_KEY }),
    ]);
  };

  const setRole = useMutation({
    mutationFn: async ({ member, role }: { member: Member; role: AssignableRole }) => {
      const { error } = await changeMemberRole({
        path: { org_id: org.id, user_id: member.user_id },
        body: { role },
      });
      if (error) throw error;
    },
    onSuccess: refresh,
  });

  const end = useMutation({
    mutationFn: async (member: Member) => {
      const { error } = await removeMember({
        path: { org_id: org.id, user_id: member.user_id },
      });
      if (error) throw error;
    },
    onSuccess: refresh,
  });

  // One refusal at a time: a role change and a removal cannot both be the last
  // thing that happened.
  const refused = setRole.error ?? end.error;
  const viewer = { role: org.role, userId: viewerId };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{org.name}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {refused ? <Callout tone="bad">{refusalMessage(refused)}</Callout> : null}
        <ul className="flex flex-col gap-2">
          {(members.data ?? []).map((member) => {
            const controls = memberControls(viewer, member);
            return (
              <li key={member.user_id} className="flex items-center gap-3">
                <span className="text-half text-ink">{memberLabel(member)}</span>
                {controls.changeRole ? (
                  <select
                    aria-label={`Role of ${memberLabel(member)}`}
                    className="h-9 rounded-md border border-line bg-panel px-2 text-half text-ink"
                    value={member.role}
                    disabled={setRole.isPending}
                    onChange={(chosen) => {
                      setRole.mutate({
                        member,
                        role: chosen.target.value as AssignableRole,
                      });
                    }}
                  >
                    <option value="member">member</option>
                    <option value="admin">admin</option>
                  </select>
                ) : (
                  <AttributeBadge>{member.role}</AttributeBadge>
                )}
                {controls.remove || controls.leave ? (
                  <Button
                    variant="link"
                    size="sm"
                    className="ml-auto px-0 text-small"
                    disabled={end.isPending}
                    onClick={() => {
                      end.mutate(member);
                    }}
                  >
                    {controls.leave ? "Leave" : "Remove"}
                  </Button>
                ) : null}
              </li>
            );
          })}
        </ul>
      </CardContent>
    </Card>
  );
}
