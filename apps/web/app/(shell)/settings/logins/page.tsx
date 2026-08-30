"use client";

import { deleteAuthState, listAuthStates, type AuthStateSummary } from "@step-by-step/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { savedLoginScope } from "./presentation";

import { Callout } from "@/components/primitives/callout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { relativeTime } from "@/lib/relative-time";

const AUTH_STATES_KEY = ["auth-states"] as const;

async function loadAuthStates(): Promise<AuthStateSummary[]> {
  const answer = await listAuthStates();
  if (answer.error) throw answer.error;
  return answer.data;
}

export default function SavedLoginsPage() {
  const authStates = useQuery({ queryKey: AUTH_STATES_KEY, queryFn: loadAuthStates });

  return (
    <div className="flex flex-col gap-4">
      {authStates.error ? <Callout tone="bad">Saved logins could not be loaded.</Callout> : null}
      {authStates.data?.length === 0 ? (
        <Card className="px-6 py-10 text-center">
          <p className="font-semibold">No saved logins</p>
          <p className="text-small text-mut">
            Logins you choose to save while recording will appear here.
          </p>
        </Card>
      ) : null}
      {authStates.data?.map((authState) => (
        <SavedLoginRow key={authState.id} authState={authState} />
      ))}
    </div>
  );
}

function SavedLoginRow({ authState }: { authState: AuthStateSummary }) {
  const cache = useQueryClient();
  const forget = useMutation({
    mutationFn: async () => {
      const answer = await deleteAuthState({ path: { auth_state_id: authState.id } });
      if (answer.error) throw answer.error;
    },
    onSuccess: async () => cache.invalidateQueries({ queryKey: AUTH_STATES_KEY }),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>{authState.domain}</CardTitle>
        <p className="text-small text-mut">
          {savedLoginScope(authState.scope)} · saved {relativeTime(authState.updated_at)}
        </p>
      </CardHeader>
      <CardContent>
        <Button variant="destructive" disabled={forget.isPending} onClick={() => forget.mutate()}>
          Forget this login
        </Button>
        {forget.error ? (
          <Callout tone="bad">This saved login could not be forgotten.</Callout>
        ) : null}
      </CardContent>
    </Card>
  );
}
