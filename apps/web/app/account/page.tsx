"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { identityQuery, signOutEverywhereAndLeave } from "@/lib/identity";

/**
 * The account panel, holding the one control this slice gives it: ending every
 * session at once.
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
        <Card>
          <CardHeader>
            <CardTitle>{me.email}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <p className="text-small text-mut">
              Signing out everywhere ends every session on every browser you are signed in on — this
              one included. Use it when you have lost a device.
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
      )}
    </main>
  );
}
