import { redirect } from "next/navigation";

import { ACCOUNT_PATH } from "@/lib/gate";

/**
 * `/settings` names no panel, and Settings is a section nav beside exactly
 * one. Account is where a bare address lands, because it is the one section
 * every role may open — the same reason the gate falls back to it.
 */
export default function SettingsPage() {
  redirect(ACCOUNT_PATH);
}
