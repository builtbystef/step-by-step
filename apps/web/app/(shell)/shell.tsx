"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useSyncExternalStore, type ReactNode } from "react";

import { AppSidebar } from "./app-sidebar";
import { PendingInvitations } from "./pending-invitations";
import { AttentionSlot } from "./slots";
import { useActiveOrganization } from "./use-active-organization";

import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { AttentionProvider } from "@/lib/attention-context";
import { ExtensionConnectionProvider } from "@/lib/extension-connection-context";
import { resolveGate } from "@/lib/gate";

const SIDEBAR_WIDTHS = {
  "--sidebar-width": "216px",
  "--sidebar-width-icon": "60px",
} as React.CSSProperties;

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

  if (me === null || away !== null) {
    return null;
  }

  return (
    <ExtensionConnectionProvider>
      <AttentionProvider>
        <SidebarProvider open={!rail} style={SIDEBAR_WIDTHS}>
          <AppSidebar me={me} active={active} here={here} />
          <SidebarInset className="min-w-0">
            <PendingInvitations me={me} />
            <AttentionSlot />
            <div className="flex min-w-0 flex-col gap-6 px-6 py-8">{children}</div>
          </SidebarInset>
        </SidebarProvider>
      </AttentionProvider>
    </ExtensionConnectionProvider>
  );
}
