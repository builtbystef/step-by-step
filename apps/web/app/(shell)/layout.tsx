import { Suspense, type ReactNode } from "react";

import { Shell } from "./shell";

export default function ShellLayout({ children }: { children: ReactNode }) {
  return (
    <Suspense>
      <Shell>{children}</Shell>
    </Suspense>
  );
}
