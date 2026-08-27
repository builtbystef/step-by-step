"use client";

import { Callout } from "@/components/primitives/callout";
import { Button } from "@/components/ui/button";

import {
  mappableHeaders,
  type ImportPanel,
  type StripPanel,
  type SummaryPanel,
} from "./csv-import";

/**
 * The mapping strip and the import summary. The page decides when to land
 * rows; this only draws the panel the import module produced.
 */

const SELECT_CLASS = "h-8 rounded-md border border-line bg-panel px-2 text-half text-ink";

export function CsvImportPanel({
  panel,
  onAssign,
  onConfirm,
  onDismiss,
  onChangeMapping,
}: {
  panel: ImportPanel;
  onAssign: (variableName: string, header: string | null) => void;
  onConfirm: () => void;
  onDismiss: () => void;
  onChangeMapping: () => void;
}) {
  if (panel.kind === "idle") {
    return null;
  }
  if (panel.kind === "strip") {
    return <MappingStrip panel={panel} onAssign={onAssign} onConfirm={onConfirm} />;
  }
  if (panel.dismissed) {
    return null;
  }
  return <ImportSummary panel={panel} onDismiss={onDismiss} onChangeMapping={onChangeMapping} />;
}

function MappingStrip({
  panel,
  onAssign,
  onConfirm,
}: {
  panel: StripPanel;
  onAssign: (variableName: string, header: string | null) => void;
  onConfirm: () => void;
}) {
  const headers = mappableHeaders(panel);
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-line bg-panel px-4 py-3">
      <p className="text-half font-semibold text-ink">Match columns to Variables</p>
      <p className="text-small text-mut">
        Suggestions are filled in but not applied until you confirm.
      </p>
      <div className="flex flex-col gap-2">
        {panel.assignment.map((entry) => (
          <label
            key={entry.variableName}
            className="flex flex-wrap items-center gap-2 text-half text-ink"
          >
            <span className="min-w-28 font-medium">{entry.variableName}</span>
            <select
              aria-label={`Column for ${entry.variableName}`}
              className={SELECT_CLASS}
              value={entry.header ?? ""}
              onChange={(chosen) => {
                onAssign(
                  entry.variableName,
                  chosen.target.value === "" ? null : chosen.target.value,
                );
              }}
            >
              <option value="">Not mapped</option>
              {headers.map((header) => (
                <option key={header} value={header}>
                  {header}
                </option>
              ))}
            </select>
            {entry.suggested ? <span className="text-small text-mut">suggested</span> : null}
          </label>
        ))}
      </div>
      {panel.droppedSecretHeaders.length > 0 ? (
        <p className="text-small text-human">
          {panel.droppedSecretHeaders
            .map((header) => `${header} was ignored and unstored`)
            .join(" · ")}
        </p>
      ) : null}
      <div>
        <Button size="sm" onClick={onConfirm}>
          Confirm mapping
        </Button>
      </div>
    </div>
  );
}

function ImportSummary({
  panel,
  onDismiss,
  onChangeMapping,
}: {
  panel: SummaryPanel;
  onDismiss: () => void;
  onChangeMapping: () => void;
}) {
  return (
    <Callout
      tone="info"
      size="banner"
      title="Imported into the grid"
      actions={
        <>
          <Button size="sm" variant="ghost" onClick={onChangeMapping}>
            Change mapping
          </Button>
          <Button size="sm" variant="secondary" onClick={onDismiss}>
            Dismiss
          </Button>
        </>
      }
    >
      <ul className="flex flex-col gap-1">
        {panel.matched.length > 0 ? (
          <li>
            Matched:{" "}
            {panel.matched.map((entry) => `${entry.variableName} ← ${entry.header}`).join(", ")}
          </li>
        ) : null}
        {panel.ignoredHeaders.length > 0 ? (
          <li>Ignored: {panel.ignoredHeaders.join(", ")}</li>
        ) : null}
        {panel.droppedSecretHeaders.length > 0 ? (
          <li>
            {panel.droppedSecretHeaders
              .map((header) => `${header} was ignored and unstored`)
              .join(" · ")}
          </li>
        ) : null}
      </ul>
    </Callout>
  );
}
