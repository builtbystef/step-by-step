"use client";

import { useMutation } from "@tanstack/react-query";

import type { OutputFormat } from "@/lib/downloads";

const FORMATS: readonly OutputFormat[] = ["json", "csv"];

/** The pair of "Download JSON / CSV" actions above an output table. */
export function OutputDownloads({
  download,
}: {
  download: (format: OutputFormat) => Promise<void>;
}) {
  const saving = useMutation({ mutationFn: download });

  return (
    <div className="flex items-center gap-3">
      {FORMATS.map((format) => (
        <button
          key={format}
          type="button"
          className="text-small font-semibold text-accent hover:underline disabled:opacity-50"
          disabled={saving.isPending}
          onClick={() => {
            saving.mutate(format);
          }}
        >
          Download {format.toUpperCase()}
        </button>
      ))}
      {saving.isError ? (
        <span className="text-small text-bad">The download did not go through. Try again.</span>
      ) : null}
    </div>
  );
}
