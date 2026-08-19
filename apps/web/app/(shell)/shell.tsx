"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useSyncExternalStore, type ReactNode } from "react";

import { AppSidebar } from "./app-sidebar";
import { PendingInvitations } from "./pending-invitations";
import { AttentionSlot } from "./slots";
import { useActiveOrganization } from "./use-active-organization";

import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { resolveGate } from "@/lib/gate";

/**
 * The frame every signed-in screen renders inside.
 *
 * It resolves the identity once, in front of everything: the gate decides from
 * that answer and the address whether a child renders at all, so a signed-out
 * visitor meets one redirect rather than a sidebar full of nav that answers
 * 401. There is no top bar — the page title is the first thing in the content
 * column, under the attention band's slot.
 */

/** The sidebar's two widths, as the spec sets them. */
const SIDEBAR_WIDTHS = {
  "--sidebar-width": "216px",
  "--sidebar-width-icon": "60px",
} as React.CSSProperties;

/**
 * At or below 1024px the labels cost more than they are worth and the sidebar
 * becomes an icon rail. It is the viewport's decision alone: there is no
 * toggle, because a rail nobody asked for is confusing in a way a rail the
 * window width explains is not.
 */
const RAIL_BELOW = "(max-width: 1024px)";

function watchRail(notify: () => void): () => void {
  const width = window.matchMedia(RAIL_BELOW);
  width.addEventListener("change", notify);
  return () => {
    width.removeEventListener("change", notify);
  };
}

export function Shell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const query = useSearchParams().toString();
  const here = query ? `${pathname}?${query}` : pathname;

  const { me, active } = useActiveOrganization();

  // Wide until the window says otherwise: nothing renders before the identity
  // arrives, so the first paint is already the browser's own answer.
  const rail = useSyncExternalStore(
    watchRail,
    () => window.matchMedia(RAIL_BELOW).matches,
    () => false,
  );

  const gate = resolveGate(me, active?.role ?? null, here);
  const away = gate.kind === "redirect" ? gate.to : null;

  useEffect(() => {
    if (away !== null) {
      router.replace(away);
    }
  }, [away, router]);

  // Nothing until the identity is known, and nothing on the way out: a shell
  // drawn over an unanswered question is a shell whose nav may be dead.
  if (me === null || away !== null) {
    return null;
  }

  return (
    <SidebarProvider open={!rail} style={SIDEBAR_WIDTHS}>
      <AppSidebar me={me} active={active} here={here} />
      <SidebarInset className="min-w-0">
        <PendingInvitations me={me} />
        <AttentionSlot />
        <div className="flex min-w-0 flex-col gap-6 px-6 py-8">{children}</div>
      </SidebarInset>
    </SidebarProvider>
  );
}
