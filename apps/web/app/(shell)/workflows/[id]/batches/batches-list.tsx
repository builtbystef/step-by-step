"use client";

import type { BatchSummary } from "@step-by-step/api-client";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { WORKFLOW_EMPTY, batchHref, listKind, rowCountLabel } from "./presentation";
import { BATCHES_PATH, fetchBatchPage } from "./queries";

import { NEW_BATCH, disabledReason } from "../../actions";
import { refusalMessage } from "../../messages";
import { workflowQuery } from "../queries";
import { newBatchPath } from "../tabs";
import { useActiveOrganization } from "../../../use-active-organization";

import { Callout } from "@/components/primitives/callout";
import { EmptyState } from "@/components/primitives/empty-state";
import { Button } from "@/components/ui/button";
import { useCursorList } from "@/hooks/use-cursor-list";
import { relativeTime } from "@/lib/relative-time";

/**
 * The Workflow's Batches. There is no global Batches index — this tab is
 * where they live. Rows navigate to the batch progress screen.
 */

export function BatchesList({ workflowId }: { workflowId: string }) {
  const { active } = useActiveOrganization();

  if (active === null) {
    return null;
  }

  return <Batches orgId={active.id} workflowId={workflowId} />;
}

function Batches({ orgId, workflowId }: { orgId: string; workflowId: string }) {
  const router = useRouter();
  const list = useCursorList<BatchSummary>({
    path: BATCHES_PATH,
    orgId,
    filters: { workflow_id: workflowId },
    fetchPage: ({ cursor, limit }) => fetchBatchPage(workflowId, cursor, limit),
    urlKeys: [],
  });
  const workflow = useQuery(workflowQuery(orgId, workflowId));
  const kind = listKind({ loaded: !list.loading, itemCount: list.items.length });
  const batchRefusal =
    workflow.data === undefined ? null : disabledReason(NEW_BATCH, workflow.data.draft_state);

  return (
    <>
      {list.error ? <Callout tone="bad">{refusalMessage(list.error)}</Callout> : null}

      {kind === "empty" ? (
        <EmptyState
          absence={WORKFLOW_EMPTY.absence}
          whatFillsIt={WORKFLOW_EMPTY.whatFillsIt}
          action={
            <Button
              disabled={batchRefusal !== null || workflow.data === undefined}
              title={batchRefusal ?? undefined}
              onClick={() => {
                router.push(newBatchPath(workflowId));
              }}
            >
              {WORKFLOW_EMPTY.action}
            </Button>
          }
        />
      ) : null}

      {kind === "rows" ? (
        <table className="w-full text-left text-half">
          <thead>
            <tr className="text-micro font-semibold tracking-wide text-mut uppercase">
              <th className="px-2 py-2">Name</th>
              <th className="px-2 py-2">Created</th>
              <th className="px-2 py-2">Rows</th>
              <th className="w-10" />
            </tr>
          </thead>
          <tbody>
            {list.items.map((batch) => (
              <BatchRow key={batch.id} batch={batch} />
            ))}
          </tbody>
        </table>
      ) : null}

      {list.hasMore ? (
        <Button
          variant="ghost"
          className="self-center text-small"
          disabled={list.fetchingMore}
          onClick={() => {
            list.loadMore();
          }}
        >
          Load more
        </Button>
      ) : null}
    </>
  );
}

function BatchRow({ batch }: { batch: BatchSummary }) {
  const href = batchHref(batch.id);

  return (
    <tr className="group relative border-t border-line hover:bg-accent-bg/40">
      <td className="px-2 py-2 font-semibold">
        <Link href={href} className="after:absolute after:inset-0 after:content-['']">
          {batch.name}
        </Link>
      </td>
      <td className="px-2 py-2 text-mut">{relativeTime(batch.created_at)}</td>
      <td className="px-2 py-2 text-mut">{rowCountLabel(batch.row_count)}</td>
      <td className="px-2 py-2">
        <ChevronRight className="ml-auto size-4 text-mut" />
      </td>
    </tr>
  );
}
