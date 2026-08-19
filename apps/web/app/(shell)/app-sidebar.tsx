"use client";

import type { Account, OrganizationMembership } from "@step-by-step/api-client";
import Link from "next/link";
import type { ReactNode } from "react";

import { isCurrentSection, NAV_DESTINATIONS, SETTINGS_DESTINATION, type Destination } from "./nav";
import { ConnectionPillSlot, RunsCountSlot } from "./slots";
import { UserMenu } from "./user-menu";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
} from "@/components/ui/sidebar";

/**
 * The frame's left edge, top to bottom: the wordmark; the three destinations;
 * a separator; Settings; a spacer; and a footer holding the extension's
 * connection pill and the user menu.
 *
 * The spacer is not an element — the content region grows to fill what the
 * header and the footer leave, which is the same thing said in one place
 * instead of two.
 */
export function AppSidebar({
  me,
  active,
  here,
}: {
  me: Account;
  active: OrganizationMembership | null;
  here: string;
}) {
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <Link
          href={NAV_DESTINATIONS[0]?.path ?? "/"}
          className="flex items-center gap-2 rounded-md p-2 outline-hidden focus-visible:ring-2 focus-visible:ring-sidebar-ring group-data-[collapsible=icon]:p-1"
        >
          <span
            aria-hidden
            className="flex size-6 shrink-0 items-center justify-center rounded-md bg-accent text-micro font-bold text-primary-foreground"
          >
            S
          </span>
          <span className="truncate text-title font-semibold text-ink group-data-[collapsible=icon]:hidden">
            Step by Step
          </span>
        </Link>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarMenu>
            {NAV_DESTINATIONS.map((destination) => (
              <NavItem key={destination.path} destination={destination} here={here}>
                {destination.path === "/runs" ? <RunsCountSlot /> : null}
              </NavItem>
            ))}
          </SidebarMenu>
        </SidebarGroup>

        <SidebarSeparator />

        <SidebarGroup>
          <SidebarMenu>
            <NavItem destination={SETTINGS_DESTINATION} here={here} />
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <ConnectionPillSlot />
        <UserMenu me={me} active={active} />
      </SidebarFooter>
    </Sidebar>
  );
}

/**
 * One nav item.
 *
 * `title` rather than a tooltip component: in the icon rail the label is gone
 * and the name has to come from somewhere, and the browser's own is the one
 * that needs nothing mounted around it.
 *
 * Anything passed as a child rides over the item rather than inside it: the
 * button clips its own contents down to the icon in the rail, and the count
 * badge is the one thing that has to survive that — a number is the whole
 * point of a rail that has no room for a word.
 */
function NavItem({
  destination,
  here,
  children,
}: {
  destination: Destination;
  here: string;
  children?: ReactNode;
}) {
  const Icon = destination.icon;

  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        isActive={isCurrentSection(here, destination.path)}
        render={<Link href={destination.path} title={destination.label} />}
      >
        <Icon />
        <span>{destination.label}</span>
      </SidebarMenuButton>
      {children ? (
        <span className="pointer-events-none absolute top-1.5 right-2 flex items-center group-data-[collapsible=icon]:top-0 group-data-[collapsible=icon]:right-2.5">
          {children}
        </span>
      ) : null}
    </SidebarMenuItem>
  );
}
