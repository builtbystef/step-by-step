import { redirect } from "next/navigation";

import { HOME_PATH } from "@/lib/gate";

/**
 * The app has no dashboard: the root is where the Workflows list lives, and
 * everything else is reached from the shell around it.
 *
 * The list itself, and the shell that puts the gate in front of it, land with
 * their own slices; until then this address is where they will be.
 */
export default function RootPage() {
  redirect(HOME_PATH);
}
