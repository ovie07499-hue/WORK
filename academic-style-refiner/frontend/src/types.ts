import type { BlockKind } from "./lib/api";

export type BlockStatus = "static" | "queued" | "rewrite" | "polish" | "done" | "error" | "regenerating";

export interface UiBlock {
  id: number;
  kind: BlockKind;
  original: string;
  refined: string | null;
  status: BlockStatus;
  warnings: string[];
  error?: string;
  /** Earlier rewrites of this block, oldest first; the latest is sent as "avoid" on regenerate. */
  history: string[];
  useOriginal: boolean;
}

export const isRewritable = (kind: BlockKind) => kind === "paragraph" || kind === "list";

export function finalText(block: UiBlock): string {
  if (block.useOriginal || block.refined === null) return block.original;
  return block.refined;
}
