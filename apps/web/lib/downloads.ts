import { getBatchOutput, getRunOutput, locateRunArtifact } from "@step-by-step/api-client";

export type OutputFormat = "json" | "csv";

// The Output and Artifact endpoints sit behind the Organization header, which an
// `<img>` or a plain link never carries. So the app asks through the typed client
// (whose interceptor adds the header), and hands what comes back to the browser.

export function saveBlob(blob: Blob, filename: string, doc: Document = document): void {
  const href = URL.createObjectURL(blob);
  const anchor = doc.createElement("a");
  anchor.href = href;
  anchor.download = filename;
  doc.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(href);
}

export function outputFilename(subject: "run" | "batch", format: OutputFormat): string {
  return `${subject}.${format}`;
}

export async function downloadRunOutput(runId: string, format: OutputFormat): Promise<void> {
  const { response } = await getRunOutput({
    path: { run_id: runId },
    query: { format },
    parseAs: "stream",
    throwOnError: true,
  });
  saveBlob(await response.blob(), outputFilename("run", format));
}

export async function downloadBatchOutput(batchId: string, format: OutputFormat): Promise<void> {
  const { response } = await getBatchOutput({
    path: { batch_id: batchId },
    query: { format },
    parseAs: "stream",
    throwOnError: true,
  });
  saveBlob(await response.blob(), outputFilename("batch", format));
}

/** A short-lived URL for one Artifact; mint it right before use. */
export async function locateArtifact(runId: string, artifactId: string): Promise<string> {
  const { data } = await locateRunArtifact({
    path: { run_id: runId, artifact_id: artifactId },
    throwOnError: true,
  });
  return data.url;
}

/** The URL is served as an attachment, so following it saves the file and leaves the page alone. */
export async function openArtifact(
  runId: string,
  artifactId: string,
  where: Pick<Location, "assign"> = window.location,
): Promise<void> {
  where.assign(await locateArtifact(runId, artifactId));
}
