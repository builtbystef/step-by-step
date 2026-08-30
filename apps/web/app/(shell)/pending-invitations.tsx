"use client";

import { acceptInvitation, type Account } from "@step-by-step/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { acceptRefusal, offerSentence } from "./messages";

import { Callout } from "@/components/primitives/callout";
import { Button } from "@/components/ui/button";
import { IDENTITY_KEY } from "@/lib/identity";

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
