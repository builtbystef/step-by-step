"use client";

import {
  acceptInvitation,
  createInvitation,
  listInvitations,
  revokeInvitation,
  type Account,
  type AssignableRole,
  type OrganizationMembership,
} from "@step-by-step/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { manageableOrgs, offerSentence, refusalMessage } from "./messages";

import { AttributeBadge } from "@/components/primitives/attribute-badge";
import { Callout } from "@/components/primitives/callout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { IDENTITY_KEY, identityQuery } from "@/lib/identity";

/**
 * Invitations, both halves: the offers standing for this visitor, and the
 * offers each of their Organizations has out.
 *
 * A temporary home. The banner belongs in the shell's chrome and the panel
 * inside Settings → Organization, and the shell slice re-homes both; until it
 * exists there is no chrome to hang them in, and an Organization cannot get
 * its second member without them.
 *
 * A signed-out visitor never sees this screen: `GET /api/auth/me` answers 401
 * and the fetch wrapper's one rule sends them to sign-in, carrying this path.
 */

/** One key per Organization, so that inviting refreshes only its own panel. */
function invitationsKey(orgId: string) {
  return ["invitations", orgId] as const;
}

export default function InvitationsPage() {
  const identity = useQuery(identityQuery());
  const me = identity.data ?? null;

  return (
    <main className="mx-auto flex w-full max-w-[720px] flex-col gap-6 px-4 py-12">
      <h1 className="text-page">Invitations</h1>
      {me === null ? null : (
        <>
          <PendingOffers me={me} />
          {manageableOrgs(me).map((org) => (
            <OrganizationPanel key={org.id} org={org} />
          ))}
        </>
      )}
    </main>
  );
}

/**
 * The banner: what a visitor has been offered, and the one action on it.
 *
 * Accepting invalidates the identity rather than patching it, because the
 * answer is 204: what the visitor now belongs to is the backend's to say.
 */
function PendingOffers({ me }: { me: Account }) {
  const cache = useQueryClient();
  const accept = useMutation({
    mutationFn: async (invitationId: string) => {
      const { error } = await acceptInvitation({ path: { invitation_id: invitationId } });
      if (error) throw error;
    },
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: IDENTITY_KEY });
    },
  });

  if (me.invitations.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-col gap-2">
      {accept.error ? <Callout tone="bad">{refusalMessage(accept.error)}</Callout> : null}
      {me.invitations.map((offer) => (
        <Callout
          key={offer.id}
          tone="info"
          size="banner"
          title="You have been invited"
          actions={
            <Button
              size="sm"
              className="text-small"
              disabled={accept.isPending}
              onClick={() => {
                accept.mutate(offer.id);
              }}
            >
              Accept
            </Button>
          }
        >
          {offerSentence(offer)}
        </Callout>
      ))}
    </div>
  );
}

/** One Organization's standing offers, with the two actions on them. */
function OrganizationPanel({ org }: { org: OrganizationMembership }) {
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
          <Label htmlFor={`invite-${org.id}`}>Invite by email</Label>
          <div className="flex items-end gap-2">
            <Input
              id={`invite-${org.id}`}
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
