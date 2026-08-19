"use client";

import { acceptInvitation, type Account } from "@step-by-step/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { acceptRefusal, offerSentence } from "./messages";

import { Callout } from "@/components/primitives/callout";
import { Button } from "@/components/ui/button";
import { IDENTITY_KEY } from "@/lib/identity";

/**
 * What is waiting on this account, said in the shell's own chrome.
 *
 * An Invitation is the one thing a person can be offered without asking for
 * it, so it surfaces wherever they are rather than on a screen they would have
 * to think to open.
 *
 * Accepting invalidates the identity rather than patching it: the answer is
 * 204, and what the visitor now belongs to is the backend's to say.
 */
export function PendingInvitations({ me }: { me: Account }) {
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
    <div className="flex flex-col gap-2 border-b border-line px-6 py-3">
      {accept.error ? <Callout tone="bad">{acceptRefusal(accept.error)}</Callout> : null}
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
