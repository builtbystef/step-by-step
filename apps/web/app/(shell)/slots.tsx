"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AttentionBand } from "@/components/primitives/attention-band";
import { ConnectionPill } from "@/components/primitives/connection-pill";
import { CountBadge } from "@/components/primitives/count-badge";
import { formatDeadline, runsBadge } from "@/lib/attention";
import { useAttention } from "@/lib/attention-context";
import { useExtensionConnection } from "@/lib/extension-connection-context";

export function AttentionSlot() {
  const router = useRouter();
  const attention = useAttention();
  const soonest = attention?.waiting[0];
  const now = useNow(soonest !== undefined);

  if (attention === null || soonest === undefined) return null;

  return (
    <AttentionBand
      waitingCount={attention.waiting_count}
      runLabel={soonest.workflow_name}
      countdown={formatDeadline(soonest.deadline_at, now)}
      onTakeControl={() => {
        router.push(`/runs/${soonest.run_id}`);
      }}
    />
  );
}

export function RunsCountSlot() {
  const attention = useAttention();
  if (attention === null) return null;

  const badge = runsBadge(attention);
  return <CountBadge count={badge.count} tone={badge.tone} />;
}

function useNow(ticking: boolean): number {
  const [now, setNow] = useState(Date.now);

  useEffect(() => {
    if (!ticking) return;
    const timer = window.setInterval(() => {
      setNow(Date.now());
    }, 1000);
    return () => {
      window.clearInterval(timer);
    };
  }, [ticking]);

  return now;
}

export function ConnectionPillSlot() {
  const connection = useExtensionConnection();
  if (connection.state === null) return null;

  return (
    <Link href="/settings/extension" title="Browser extension">
      <ConnectionPill state={connection.state} version={connection.version ?? undefined} />
    </Link>
  );
}
