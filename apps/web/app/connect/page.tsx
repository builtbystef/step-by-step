import { Suspense } from "react";

import { ConnectScreen } from "./connect-screen";

/**
 * `/connect` — where the extension is told which instance this is.
 *
 * The screen reads the extension's nonce out of the query, which is a
 * client-side fact; the Suspense boundary is what lets the rest of the page be
 * prerendered anyway.
 */
export default function ConnectPage() {
  return (
    <Suspense>
      <ConnectScreen />
    </Suspense>
  );
}
