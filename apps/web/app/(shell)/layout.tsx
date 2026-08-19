import { Suspense, type ReactNode } from "react";

import { Shell } from "./shell";

/**
 * Every route but `/signin` renders inside the shell.
 *
 * The shell reads the address it is on, query and all, because that is what
 * the gate carries as `next`; the Suspense boundary is what lets the rest of
 * the page be prerendered anyway.
 */
export default function ShellLayout({ children }: { children: ReactNode }) {
  return (
    <Suspense>
      <Shell>{children}</Shell>
    </Suspense>
  );
}
