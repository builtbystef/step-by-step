"use client";

import {
  deleteOrganization,
  renameOrganization,
  transferOwnership,
  type Member,
  type OrganizationMembership,
} from "@step-by-step/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { membersKey, membersQuery } from "./queries";

import {
  endingConsequence,
  mayEnd,
  mayRename,
  memberControls,
  memberLabel,
  nameConfirms,
  refusalMessage,
  transferConsequence,
} from "./messages";

import { useActiveOrganization } from "../../use-active-organization";

import { Callout } from "@/components/primitives/callout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { IDENTITY_KEY } from "@/lib/identity";

/**
 * Settings → Organization → General: what the active Organization is called,
 * and the two acts it has exactly one person for.
 *
 * A member reads its name and nothing else. Renaming is the owner's and the
 * admins'; handing it on and ending it are the owner's alone. Each rule is the
 * backend's, said again so that a control nobody may use is not offered.
 */
export default function OrganizationGeneralPage() {
  const { me, active } = useActiveOrganization();

  if (me === null || active === null) {
    return null;
  }

  return (
    <>
      <Name org={active} />
      {mayEnd(active.role) ? (
        <>
          <HandItOn org={active} viewerId={me.id} />
          <EndIt org={active} />
        </>
      ) : null}
    </>
  );
}

/** What the Organization is called, and who may change it. */
function Name({ org }: { org: OrganizationMembership }) {
  const cache = useQueryClient();
  const [name, setName] = useState(org.name);

  const rename = useMutation({
    mutationFn: async () => {
      const { error } = await renameOrganization({ path: { org_id: org.id }, body: { name } });
      if (error) throw error;
    },
    // The identity carries every Organization's name, and the sidebar reads
    // the active one's from it.
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: IDENTITY_KEY });
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>{org.name}</CardTitle>
      </CardHeader>
      <CardContent>
        {mayRename(org.role) ? (
          <form
            className="flex flex-col gap-3"
            onSubmit={(submitted) => {
              submitted.preventDefault();
              rename.mutate();
            }}
          >
            <Label htmlFor="org-name">Name</Label>
            <div className="flex items-end gap-2">
              <Input
                id="org-name"
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
            {rename.error ? <Callout tone="bad">{refusalMessage(rename.error)}</Callout> : null}
          </form>
        ) : (
          <p className="text-small text-mut">
            An owner or an admin can rename this Organization. You are a member of it.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * Handing the Organization on.
 *
 * The person who asks for this is the person who stops being the owner, which
 * is the half nobody expects — so it is said before it is done, naming who
 * they are handing it to.
 */
function HandItOn({ org, viewerId }: { org: OrganizationMembership; viewerId: string }) {
  const cache = useQueryClient();
  const [chosen, setChosen] = useState("");
  const [confirming, setConfirming] = useState(false);

  const members = useQuery(membersQuery(org.id));
  const eligible = (members.data ?? []).filter(
    (member) => memberControls({ role: org.role, userId: viewerId }, member).makeOwner,
  );
  const handingTo = eligible.find((member) => member.user_id === chosen) ?? null;

  const hand = useMutation({
    mutationFn: async (member: Member) => {
      const { error } = await transferOwnership({
        path: { org_id: org.id },
        body: { user_id: member.user_id },
      });
      if (error) throw error;
    },
    onSuccess: async () => {
      setConfirming(false);
      setChosen("");
      await Promise.all([
        cache.invalidateQueries({ queryKey: membersKey(org.id) }),
        cache.invalidateQueries({ queryKey: IDENTITY_KEY }),
      ]);
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Transfer ownership</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {eligible.length === 0 ? (
          <p className="text-small text-mut">
            There is nobody else in {org.name} to hand it to. Invite somebody first.
          </p>
        ) : (
          <div className="flex items-end gap-2">
            <select
              aria-label="Who becomes the owner"
              className="h-9 rounded-md border border-line bg-panel px-2 text-half text-ink"
              value={chosen}
              onChange={(picked) => {
                setConfirming(false);
                setChosen(picked.target.value);
              }}
            >
              <option value="">Choose somebody</option>
              {eligible.map((member) => (
                <option key={member.user_id} value={member.user_id}>
                  {memberLabel(member)}
                </option>
              ))}
            </select>
            <Button
              disabled={handingTo === null}
              onClick={() => {
                setConfirming(true);
              }}
            >
              Hand it on
            </Button>
          </div>
        )}

        {hand.error ? <Callout tone="bad">{refusalMessage(hand.error)}</Callout> : null}

        {confirming && handingTo ? (
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
                    setConfirming(false);
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
      </CardContent>
    </Card>
  );
}

/** Ending the Organization, behind typing its name. */
function EndIt({ org }: { org: OrganizationMembership }) {
  const cache = useQueryClient();
  const [typedName, setTypedName] = useState("");

  const finish = useMutation({
    mutationFn: async () => {
      const { error } = await deleteOrganization({
        path: { org_id: org.id },
        body: { name_confirmation: typedName },
      });
      if (error) throw error;
    },
    // Nothing to reset afterwards: the identity comes back without this
    // Organization in it, the switcher resolves to another, and everything
    // read through the old one is read again.
    onSuccess: async () => {
      await cache.invalidateQueries();
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Delete this Organization</CardTitle>
      </CardHeader>
      <CardContent>
        <form
          className="flex flex-col gap-3"
          onSubmit={(submitted) => {
            submitted.preventDefault();
            finish.mutate();
          }}
        >
          <Callout tone="bad">{endingConsequence(org.name)}</Callout>
          {finish.error ? <Callout tone="bad">{refusalMessage(finish.error)}</Callout> : null}
          <Label htmlFor="confirm-org-name">Type {org.name} to confirm</Label>
          <div className="flex items-end gap-2">
            <Input
              id="confirm-org-name"
              value={typedName}
              autoComplete="off"
              onChange={(typed) => {
                setTypedName(typed.target.value);
              }}
            />
            <Button
              type="submit"
              variant="destructive"
              disabled={finish.isPending || !nameConfirms(typedName, org.name)}
            >
              Delete Organization
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
