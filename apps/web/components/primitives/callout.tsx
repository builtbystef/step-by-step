import type { ReactNode } from "react";

import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { cn } from "@/lib/utils";

export type CalloutTone = "info" | "warn" | "bad" | "ok" | "secret";

export type CalloutSize = "inline" | "banner";

const TONE_CLASSES: Record<CalloutTone, string> = {
  info: "border-accent/30 bg-accent-bg text-accent",
  warn: "border-wait/30 bg-wait-bg text-wait",
  bad: "border-bad/30 bg-bad-bg text-bad",
  ok: "border-ok/30 bg-ok-bg text-ok",
  secret: "border-human/30 bg-human-bg text-human",
};

const SIZE_CLASSES: Record<CalloutSize, string> = {
  inline: "px-3 py-2",
  banner: "w-full px-4 py-3",
};

export function Callout({
  tone,
  size = "inline",
  icon,
  title,
  actions,
  className,
  children,
}: {
  tone: CalloutTone;
  size?: CalloutSize;
  icon?: ReactNode;
  title?: ReactNode;
  actions?: ReactNode;
  className?: string;
  children?: ReactNode;
}) {
  return (
    <Alert className={cn("text-half", TONE_CLASSES[tone], SIZE_CLASSES[size], className)}>
      {icon}
      {title ? <AlertTitle className="font-semibold">{title}</AlertTitle> : null}
      {children ? (
        <AlertDescription className="text-half text-current">{children}</AlertDescription>
      ) : null}
      {actions ? <AlertAction className="flex items-center gap-2">{actions}</AlertAction> : null}
    </Alert>
  );
}
