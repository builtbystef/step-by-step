import { Suspense } from "react";

import { ConnectScreen } from "./connect-screen";

export default function ConnectPage() {
  return (
    <Suspense>
      <ConnectScreen />
    </Suspense>
  );
}
