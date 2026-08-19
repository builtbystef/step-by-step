"use client";

import {
  changeMemberRole,
  listMembers,
  removeMember,
  renameOrganization,
  transferOwnership,
  type AssignableRole,
  type Account,
  type Member,
  type OrganizationMembership,
} from "@step-by-step/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  mayRename,
  memberControls,
  memberLabel,
  refusalMessage,
  transferConsequence,
} from "./messages";

import { AttributeBadge } from "@/components/primitives/attribute-badge";
import { Callout } from "@/components/primitives/callout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { IDENTITY_KEY, identityQuery } from "@/lib/identity";

/**
 * Each Organization this visitor is in: its name, and who is in it.
 *
 * A temporary home, like the Invitations screen beside it. The rename belongs
 * in Settings → Organization → General and the member list in Members, and the
 * shell slice re-homes both; until it exists there is no Settings to put them
 * in, and a team that cannot change a role or remove somebody is a team locked
 * into whatever its first day left behind.
 *
 * A signed-out visitor never sees this screen: `GET /api/auth/me` answers 401
 * and the fetch wrapper's one rule sends them to sign-in, carrying this path.
 */

/** One key per Organization, so that an action refreshes only its own panel. */
function membersKey(orgId: string) {
  return ["members", orgId] as const;
}

export default function OrganizationPage() {
  const identity = useQuery(identityQuery());
  const me = identity.data ?? null;

  return (
    <main className="mx-auto flex w-full max-w-[720px] flex-col gap-6 px-4 py-12">
      <h1 className="text-page">Organizations</h1>
      {me === null
        ? null
        : me.orgs.map((org) => <OrganizationPanel key={org.id} me={me} org={org} />)}
    </main>
  );
}

/** One Organization: what it is called, and everybody in it. */
function OrganizationPanel({ me, org }: { me: Account; org: OrganizationMembership }) {
  const cache = useQueryClient();
  const [name, setName] = useState(org.name);
  const [handingTo, setHandingTo] = useState<Member | null>(null);

  const members = useQuery({
    queryKey: membersKey(org.id),
    queryFn: async () => (await listMembers({ path: { org_id: org.id } })).data ?? [],
  });

  /**
   * Both keys, always. A role, a removal, and a rename each change what the
   * identity says about this visitor — which Organizations they are in and
   * what they may do there — and the screen reads its own place from it.
   */
  const refresh = async () => {
    await Promise.all([
      cache.invalidateQueries({ queryKey: membersKey(org.id) }),
      cache.invalidateQueries({ queryKey: IDENTITY_KEY }),
    ]);
  };

  const rename = useMutation({
    mutationFn: async () => {
      const { error } = await renameOrganization({ path: { org_id: org.id }, body: { name } });
      if (error) throw error;
    },
    onSuccess: refresh,
  });

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

  const hand = useMutation({
    mutationFn: async (member: Member) => {
      const { error } = await transferOwnership({
        path: { org_id: org.id },
        body: { user_id: member.user_id },
      });
      if (error) throw error;
    },
    onSuccess: async () => {
      setHandingTo(null);
      await refresh();
    },
  });

  // One refusal at a time: only one of these was the last thing that happened.
  const refused = rename.error ?? setRole.error ?? end.error ?? hand.error;
  const viewer = { role: org.role, userId: me.id };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{org.name}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {mayRename(org.role) ? (
          <form
            className="flex flex-col gap-3"
            onSubmit={(submitted) => {
              submitted.preventDefault();
              rename.mutate();
            }}
          >
            <Label htmlFor={`name-${org.id}`}>Name</Label>
            <div className="flex items-end gap-2">
              <Input
                id={`name-${org.id}`}
                value={name}
                onChange={(typed) => {
                  setName(typed.target.value);
                }}
              />
              <Button
                type="submit"
                disabled={rename.isPending || name.trim().length === 0 || name === org.name}
              >
                Rename
              </Button>
            </div>
          </form>
        ) : null}

        {refused ? <Callout tone="bad">{refusalMessage(refused)}</Callout> : null}

        {handingTo ? (
          <Callout
            tone="warn"
            title="Hand the Organization on?"
            actions={
              <div className="flex gap-2">
                <Button
                  size="sm"
                  className="text-small"
                  disabled={hand.isPending}
                  onClick={() => {
                    hand.mutate(handingTo);
                  }}
                >
                  Hand it on
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-small"
                  onClick={() => {
                    setHandingTo(null);
                  }}
                >
                  Cancel
                </Button>
              </div>
            }
          >
            {transferConsequence(handingTo, org.name)}
          </Callout>
        ) : null}

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
                <span className="ml-auto flex items-center gap-3">
                  {controls.makeOwner ? (
                    <Button
                      variant="link"
                      size="sm"
                      className="px-0 text-small"
                      onClick={() => {
                        setHandingTo(member);
                      }}
                    >
                      Make owner
                    </Button>
                  ) : null}
                  {controls.remove || controls.leave ? (
                    <Button
                      variant="link"
                      size="sm"
                      className="px-0 text-small"
                      disabled={end.isPending}
                      onClick={() => {
                        end.mutate(member);
                      }}
                    >
                      {controls.leave ? "Leave" : "Remove"}
                    </Button>
                  ) : null}
                </span>
              </li>
            );
          })}
        </ul>
      </CardContent>
    </Card>
  );
}
