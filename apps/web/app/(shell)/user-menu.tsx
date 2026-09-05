"use client";

import type { Account, OrganizationMembership } from "@step-by-step/api-client";
import { useQueryClient } from "@tanstack/react-query";
import { ChevronsUpDown } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { SETTINGS_DESTINATION } from "./nav";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { chooseOrganization, offersASwitcher } from "@/lib/active-org";
import { signOutAndLeave } from "@/lib/identity";
import { chooseTheme, isThemeChoice, THEME_CHOICES } from "@/lib/theme";
import { useThemeChoice } from "@/lib/use-theme-choice";

export function UserMenu({ me, active }: { me: Account; active: OrganizationMembership | null }) {
  const router = useRouter();
  const cache = useQueryClient();
  const name = me.display_name ?? me.email;
  const theme = useThemeChoice();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex w-full items-center gap-2 rounded-md p-2 text-left outline-hidden hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-2 focus-visible:ring-sidebar-ring group-data-[collapsible=icon]:size-8! group-data-[collapsible=icon]:p-1!">
        <span
          aria-hidden
          className="flex size-6 shrink-0 items-center justify-center rounded-md bg-accent-bg text-micro font-semibold text-accent uppercase"
        >
          {name.slice(0, 1)}
        </span>
        <span className="flex min-w-0 flex-col group-data-[collapsible=icon]:hidden">
          <span className="truncate text-half font-semibold text-ink">{name}</span>
          <span className="truncate text-micro text-mut">{active?.name ?? me.email}</span>
        </span>
        <ChevronsUpDown className="ml-auto size-4 shrink-0 text-mut group-data-[collapsible=icon]:hidden" />
      </DropdownMenuTrigger>

      <DropdownMenuContent side="top" align="start" className="w-60">
        <DropdownMenuGroup>
          <DropdownMenuLabel className="flex flex-col">
            <span className="text-half text-ink">{name}</span>
            {name === me.email ? null : <span className="text-micro text-mut">{me.email}</span>}
          </DropdownMenuLabel>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />

        <DropdownMenuGroup>
          <DropdownMenuLabel>Organizations</DropdownMenuLabel>
          {offersASwitcher(me) ? (
            <DropdownMenuRadioGroup
              value={active?.id ?? ""}
              onValueChange={(chosen) => {
                chooseOrganization(chosen);
                void cache.invalidateQueries();
              }}
            >
              {me.orgs.map((org) => (
                <DropdownMenuRadioItem key={org.id} value={org.id}>
                  {org.name}
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
          ) : (
            <p className="px-1.5 py-1 text-half text-ink">{active?.name}</p>
          )}
        </DropdownMenuGroup>

        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuLabel>Appearance</DropdownMenuLabel>
          <DropdownMenuRadioGroup
            value={theme}
            onValueChange={(chosen) => {
              if (isThemeChoice(chosen)) {
                chooseTheme(chosen);
              }
            }}
          >
            {THEME_CHOICES.map((choice) => (
              <DropdownMenuRadioItem key={choice.value} value={choice.value}>
                {choice.label}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuGroup>

        <DropdownMenuSeparator />
        <DropdownMenuItem render={<Link href={SETTINGS_DESTINATION.path} />}>
          {SETTINGS_DESTINATION.label}
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => {
            void signOutAndLeave(cache, (to) => {
              router.replace(to);
            });
          }}
        >
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
