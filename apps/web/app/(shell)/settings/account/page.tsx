"use client";

import { updateAccount, type Account } from "@step-by-step/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import {
  emailConfirms,
  endingConsequence,
  ownedOrganizations,
  refusalMessage,
  soleOwnerExplanation,
} from "./messages";

import { useActiveOrganization } from "../../use-active-organization";

import { Callout } from "@/components/primitives/callout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { deleteAccountAndLeave, IDENTITY_KEY, signOutEverywhereAndLeave } from "@/lib/identity";

/**
 * Settings → Account: everything that is about the person rather than about a
 * team they are in — what they are called, ending every session at once, and
 * ending the account itself.
 *
 * Signing out of this browser alone is not here. It is in the sidebar's user
 * menu, because leaving is not a setting.
 */
export default function AccountPage() {
  const { me } = useActiveOrganization();

  if (me === null) {
    return null;
  }

  return (
    <>
      <DisplayName me={me} />
      <EverySession />
      <DangerZone me={me} />
    </>
  );
}

/** What this person is called, wherever the app names them. */
function DisplayName({ me }: { me: Account }) {
  const cache = useQueryClient();
  const [name, setName] = useState(me.display_name ?? "");

  const rename = useMutation({
    mutationFn: async () => {
      const { error } = await updateAccount({ body: { display_name: name.trim() || null } });
      if (error) throw error;
    },
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: IDENTITY_KEY });
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>{me.email}</CardTitle>
      </CardHeader>
      <CardContent>
        <form
          className="flex flex-col gap-3"
          onSubmit={(submitted) => {
            submitted.preventDefault();
            rename.mutate();
          }}
        >
          <Label htmlFor="display-name">Display name</Label>
          <p className="text-small text-mut">
            What the app calls you. The address above is what identifies the account, and it does
            not change.
          </p>
          <div className="flex items-end gap-2">
            <Input
              id="display-name"
              value={name}
              autoComplete="name"
              onChange={(typed) => {
                setName(typed.target.value);
              }}
            />
            <Button
              type="submit"
              disabled={rename.isPending || name.trim() === (me.display_name ?? "")}
            >
              Save
            </Button>
          </div>
          {rename.error ? <Callout tone="bad">{refusalMessage(rename.error)}</Callout> : null}
        </form>
      </CardContent>
    </Card>
  );
}

/** The one action that reaches past this browser without ending anything. */
function EverySession() {
  const router = useRouter();
  const cache = useQueryClient();

  const signOutEverywhere = useMutation({
    mutationFn: () =>
      signOutEverywhereAndLeave(cache, (to) => {
        router.replace(to);
      }),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Sessions</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <p className="text-small text-mut">
          Signing out everywhere ends every session on every browser you are signed in on — this one
          included. Use it when you have lost a device.
        </p>
        <Button
          variant="destructive"
          className="self-start"
          disabled={signOutEverywhere.isPending}
          onClick={() => {
            signOutEverywhere.mutate();
          }}
        >
          Sign out everywhere
        </Button>
      </CardContent>
    </Card>
  );
}

/**
 * Ending the account, behind typing its address.
 *
 * An account that still owns an Organization is shown what stands in the way
 * and where to go about it instead of a form it cannot use: the refusal it
 * would meet is one the person can act on, so the screen says it first.
 */
function DangerZone({ me }: { me: Account }) {
  const router = useRouter();
  const cache = useQueryClient();
  const [typed, setTyped] = useState("");
  const owned = ownedOrganizations(me);

  const end = useMutation({
    mutationFn: () =>
      deleteAccountAndLeave(
        cache,
        (to) => {
          router.replace(to);
        },
        typed,
      ),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Delete this account</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Callout tone="bad">{endingConsequence()}</Callout>
        {end.error ? <Callout tone="bad">{refusalMessage(end.error)}</Callout> : null}
        {owned.length > 0 ? (
          <Callout
            tone="warn"
            title="Hand your Organizations on first"
            actions={
              <Button
                size="sm"
                variant="ghost"
                className="text-small"
                onClick={() => {
                  router.push("/settings/organization/members");
                }}
              >
                Go to Members
              </Button>
            }
          >
            {soleOwnerExplanation(owned)}
          </Callout>
        ) : (
          <form
            className="flex flex-col gap-3"
            onSubmit={(submitted) => {
              submitted.preventDefault();
              end.mutate();
            }}
          >
            <Label htmlFor="confirm-email">Type {me.email} to confirm</Label>
            <div className="flex items-end gap-2">
              <Input
                id="confirm-email"
                value={typed}
                autoComplete="off"
                onChange={(entered) => {
                  setTyped(entered.target.value);
                }}
              />
              <Button
                type="submit"
                variant="destructive"
                disabled={end.isPending || !emailConfirms(typed, me.email)}
              >
                Delete account
              </Button>
            </div>
          </form>
        )}
      </CardContent>
    </Card>
  );
}
