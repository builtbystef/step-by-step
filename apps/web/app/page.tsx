import { redirect } from "next/navigation";

import { HOME_PATH } from "@/lib/gate";

export default function RootPage() {
  redirect(HOME_PATH);
}
