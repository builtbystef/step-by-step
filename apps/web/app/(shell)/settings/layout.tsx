"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { settingsNav } from "./sections";

import { useActiveOrganization } from "../use-active-organization";

import { cn } from "@/lib/utils";

export default function SettingsLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { active } = useActiveOrganization();
  const groups = settingsNav(active?.role ?? null);

  return (
    <>
      <h1 className="text-page">Settings</h1>
      <div className="flex flex-col gap-8 md:flex-row">
        <nav aria-label="Settings" className="flex shrink-0 flex-col gap-4 md:w-[180px]">
          {groups.map((group, index) => (
            <div key={group.label ?? `group-${String(index)}`} className="flex flex-col gap-0.5">
              {group.label ? (
                <span className="px-2 py-1 text-micro font-semibold text-mut uppercase">
                  {group.label}
                </span>
              ) : null}
              {group.sections.map((section) => (
                <Link
                  key={section.path}
                  href={section.path}
                  aria-current={pathname === section.path ? "page" : undefined}
                  className={cn(
                    "rounded-md px-2 py-1.5 text-half text-ink hover:bg-accent-bg",
                    pathname === section.path && "bg-accent-bg font-semibold text-accent",
                  )}
                >
                  {section.label}
                </Link>
              ))}
            </div>
          ))}
        </nav>
        <div className="flex min-w-0 flex-1 flex-col gap-6">{children}</div>
      </div>
    </>
  );
}
