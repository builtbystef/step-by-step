"use client";

import {
  createInvitation,
  listInvitations,
  revokeInvitation,
  type AssignableRole,
  type OrganizationMembership,
} from "@step-by-step/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { refusalMessage } from "./messages";

import { useActiveOrganization } from "../../../use-active-organization";

import { AttributeBadge } from "@/components/primitives/attribute-badge";
import { Callout } from "@/components/primitives/callout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/**
 * Settings → Organization → Invitations: the offers the active Organization
 * has out, and the two things to do about one.
 *
 * An owner's and an admin's section. A member never reaches it — the nav does
 * not offer it and the gate sends the address to Account — so nothing here
 * asks again what role is reading it.
 *
 * The offers standing for the person rather than for the team are the shell's:
 * an Invitation you have been sent finds you wherever you are.
 */

/** One key per Organization, so that inviting refreshes only its own list. */
function invitationsKey(orgId: string) {
  return ["invitations", orgId] as const;
}

export default function InvitationsPage() {
  const { active } = useActiveOrganization();

  if (active === null) {
    return null;
  }

  return <Invitations org={active} />;
}

function Invitations({ org }: { org: OrganizationMembership }) {
  const cache = useQueryClient();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<AssignableRole>("member");

  const standing = useQuery({
    queryKey: invitationsKey(org.id),
    queryFn: async () => (await listInvitations({ path: { org_id: org.id } })).data ?? [],
  });

  const refresh = async () => {
    await cache.invalidateQueries({ queryKey: invitationsKey(org.id) });
  };

  const send = useMutation({
    mutationFn: async () => {
      const { error } = await createInvitation({
        path: { org_id: org.id },
        body: { email, role },
      });
      if (error) throw error;
    },
    onSuccess: async () => {
      setEmail("");
      await refresh();
    },
  });

  const withdraw = useMutation({
    mutationFn: async (invitationId: string) => {
      const { error } = await revokeInvitation({
        path: { org_id: org.id, invitation_id: invitationId },
      });
      if (error) throw error;
    },
    onSuccess: refresh,
  });

  // One refusal at a time: sending and withdrawing cannot both be the last
  // thing that happened.
  const refused = send.error ?? withdraw.error;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{org.name}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <form
          className="flex flex-col gap-3"
          onSubmit={(submitted) => {
            submitted.preventDefault();
            send.mutate();
          }}
        >
          <Label htmlFor="invite-email">Invite by email</Label>
          <div className="flex items-end gap-2">
            <Input
              id="invite-email"
              type="email"
              value={email}
              autoComplete="off"
              onChange={(typed) => {
                setEmail(typed.target.value.trim());
              }}
            />
            <select
              aria-label="Role"
              className="h-9 rounded-md border border-line bg-panel px-2 text-half text-ink"
              value={role}
              onChange={(chosen) => {
                setRole(chosen.target.value as AssignableRole);
              }}
            >
              <option value="member">member</option>
              <option value="admin">admin</option>
            </select>
            <Button type="submit" disabled={send.isPending || email.length === 0}>
              Invite
            </Button>
          </div>
          {refused ? <Callout tone="bad">{refusalMessage(refused)}</Callout> : null}
        </form>

        {standing.data === undefined || standing.data.length === 0 ? (
          <p className="text-small text-mut">No Invitation is standing.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {standing.data.map((invitation) => (
              <li key={invitation.id} className="flex items-center gap-3">
                <span className="text-half text-ink">{invitation.email}</span>
                <AttributeBadge>{invitation.role}</AttributeBadge>
                <Button
                  variant="link"
                  size="sm"
                  className="ml-auto px-0 text-small"
                  disabled={withdraw.isPending}
                  onClick={() => {
                    withdraw.mutate(invitation.id);
                  }}
                >
                  Revoke
                </Button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
