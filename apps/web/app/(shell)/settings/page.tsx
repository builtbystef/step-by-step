import { redirect } from "next/navigation";

import { ACCOUNT_PATH } from "@/lib/gate";

export default function SettingsPage() {
  redirect(ACCOUNT_PATH);
}
