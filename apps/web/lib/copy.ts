/**
 * The sentences that must be identical across screens.
 *
 * A sentence earns a place here when two surfaces would otherwise phrase the
 * same fact twice and drift apart. Everything else belongs to its screen.
 */
export const COPY = {
  /**
   * Shown wherever Run, New batch, and New schedule are disabled because the
   * Workflow has no published Version: the list row, the Workflow header, both
   * creation pages, and as the rendering of a `409 no_published_version`.
   */
  noPublishedVersion: "Publish a Version before this Workflow can run.",
} as const;
