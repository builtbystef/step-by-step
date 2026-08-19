"use client";

import type { Account } from "@step-by-step/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import {
  emailConfirms,
  endingConsequence,
  ownedOrganizations,
  refusalMessage,
  soleOwnerExplanation,
} from "./messages";

import { Callout } from "@/components/primitives/callout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { deleteAccountAndLeave, identityQuery, signOutEverywhereAndLeave } from "@/lib/identity";

/**
 * The account panel, holding the two controls this slice gives it: ending
 * every session at once, and ending the account itself.
 *
 * A temporary home, like the Invitations screen beside it. Settings → Account
 * is where these controls belong, and the shell slice re-homes them there;
 * until it exists there is no Settings to put them in, and a person who has
 * lost a device needs the action before they need a sidebar.
 *
 * A signed-out visitor never sees this screen: `GET /api/auth/me` answers 401
 * and the fetch wrapper's one rule sends them to sign-in, carrying this path.
 */
export default function AccountPage() {
  const router = useRouter();
  const cache = useQueryClient();
  const identity = useQuery(identityQuery());
  const me = identity.data ?? null;

  const signOutEverywhere = useMutation({
    mutationFn: () => signOutEverywhereAndLeave(cache, (to) => router.replace(to)),
  });

  return (
    <main className="mx-auto flex w-full max-w-[720px] flex-col gap-6 px-4 py-12">
      <h1 className="text-page">Account</h1>
      {me === null ? null : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>{me.email}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <p className="text-small text-mut">
                Signing out everywhere ends every session on every browser you are signed in on —
                this one included. Use it when you have lost a device.
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
          <DangerZone me={me} />
        </>
      )}
    </main>
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
    mutationFn: () => deleteAccountAndLeave(cache, (to) => router.replace(to), typed),
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
                  router.push("/organization");
                }}
              >
                Go to your Organizations
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
