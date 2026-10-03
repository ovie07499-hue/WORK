import { diffWordsWithSpace } from "diff";

export interface DiffPart {
  value: string;
  type: "same" | "added" | "removed";
}

export function wordDiff(before: string, after: string): DiffPart[] {
  return diffWordsWithSpace(before, after).map((part) => ({
    value: part.value,
    type: part.added ? "added" : part.removed ? "removed" : "same",
  }));
}

/** Share of the original words that were changed or removed (0-1). */
export function changeRatio(before: string, after: string): number {
  const total = countWords(before);
  if (!total) return 0;
  const removed = wordDiff(before, after)
    .filter((p) => p.type === "removed")
    .reduce((n, p) => n + countWords(p.value), 0);
  return Math.min(1, removed / total);
}

export function countWords(text: string): number {
  return text.match(/[\p{L}\p{N}]+(?:['’-][\p{L}\p{N}]+)*/gu)?.length ?? 0;
}
