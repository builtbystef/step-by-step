import type { ReactNode } from "react";

import { Card, CardContent } from "@/components/ui/card";

/**
 * A panel for a destination the shell routes to before the slice that fills it
 * has landed.
 *
 * It says what will be here and which spec brings it, because the alternative
 * — an empty screen, or an `EmptyState` claiming the visitor has none of
 * something — would say something untrue about their own data.
 */
export function Placeholder({ children }: { children: ReactNode }) {
  return (
    <Card>
      <CardContent className="py-8">
        <p className="text-half text-mut">{children}</p>
      </CardContent>
    </Card>
  );
}
