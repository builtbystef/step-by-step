"use client";

import type { Account, OrganizationMembership } from "@step-by-step/api-client";
import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

import { isCurrentSection, NAV_DESTINATIONS, type Destination } from "./nav";
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
} from "@/components/ui/sidebar";

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
      <SidebarHeader className="border-b border-sidebar-border">
        <Link
          href={NAV_DESTINATIONS[0]?.path ?? "/"}
          aria-label="Step by Step"
          className="flex items-center gap-2.5 rounded-md p-2 outline-hidden focus-visible:ring-2 focus-visible:ring-sidebar-ring group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:p-1"
        >
          <Image
            src="/brand/logo-icon.svg"
            alt=""
            aria-hidden
            width={28}
            height={28}
            className="size-7 shrink-0"
          />
          <Image
            src="/brand/logo-wordmark.svg"
            alt=""
            aria-hidden
            width={94}
            height={16}
            className="h-4 w-auto group-data-[collapsible=icon]:hidden"
          />
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
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border">
        <div className="px-2 group-data-[collapsible=icon]:hidden">
          <ConnectionPillSlot />
        </div>
        <UserMenu me={me} active={active} />
      </SidebarFooter>
    </Sidebar>
  );
}

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
