import type { ReactNode } from "react";

import { Card, CardContent } from "@/components/ui/card";

export function Placeholder({ children }: { children: ReactNode }) {
  return (
    <Card>
      <CardContent className="py-8">
        <p className="text-half text-mut">{children}</p>
      </CardContent>
    </Card>
  );
}
