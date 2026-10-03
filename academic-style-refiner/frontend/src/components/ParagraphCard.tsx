import { useMemo, useState } from "react";
import { changeRatio, wordDiff } from "../lib/diff";
import { finalText, isRewritable, type UiBlock } from "../types";

export type ViewMode = "side" | "inline";

interface Props {
  block: UiBlock;
  index: number;
  viewMode: ViewMode;
  canRegenerate: boolean;
  onRegenerate: () => void;
  onToggleOriginal: () => void;
}

const STATUS_LABEL: Record<UiBlock["status"], string> = {
  static: "",
  queued: "Queued",
  rewrite: "Rewriting…",
  polish: "Polishing…",
  done: "",
  error: "Failed",
  regenerating: "Regenerating…",
};

function Text({ text, kind }: { text: string; kind: UiBlock["kind"] }) {
  return <div className={`prose-academic ${kind === "list" ? "whitespace-pre-line" : ""}`}>{text}</div>;
}

export function ParagraphCard({ block, index, viewMode, canRegenerate, onRegenerate, onToggleOriginal }: Props) {
  const [copied, setCopied] = useState(false);
  const parts = useMemo(
    () => (block.refined !== null ? wordDiff(block.original, block.refined) : null),
    [block.original, block.refined],
  );
  const ratio = useMemo(
    () => (block.refined !== null ? changeRatio(block.original, block.refined) : 0),
    [block.original, block.refined],
  );

  if (!isRewritable(block.kind)) {
    if (block.kind === "heading") {
      return (
        <h3 className="px-1 pt-4 font-serif text-lg font-semibold text-ink-900">{block.original.replace(/^#+\s*/, "")}</h3>
      );
    }
    return (
      <div className="rounded-lg border border-dashed border-ink-200 px-4 py-2 text-sm text-ink-500">
        <span className="mr-2 text-[10px] font-semibold uppercase tracking-wide">Reference · unchanged</span>
        {block.original}
      </div>
    );
  }

  const busy = ["queued", "rewrite", "polish", "regenerating"].includes(block.status);
  const hasResult = block.refined !== null;

  const original = (
    <div>
      <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-ink-500">Original</p>
      <div className={`prose-academic ${block.kind === "list" ? "whitespace-pre-line" : ""}`}>
        {parts
          ? parts.map((p, i) =>
              p.type === "added" ? null : p.type === "removed" ? (
                <del key={i} className="diff-del">
                  {p.value}
                </del>
              ) : (
                <span key={i}>{p.value}</span>
              ),
            )
          : block.original}
      </div>
    </div>
  );

  const refined = (
    <div>
      <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-navy-600">
        Refined{block.useOriginal && " (not used, original kept)"}
      </p>
      {busy && !hasResult ? (
        <div className="animate-pulse-soft space-y-2 pt-1" aria-hidden>
          <div className="h-3 w-11/12 rounded bg-ink-100" />
          <div className="h-3 w-full rounded bg-ink-100" />
          <div className="h-3 w-4/5 rounded bg-ink-100" />
        </div>
      ) : block.status === "error" && !hasResult ? (
        <p className="text-sm text-rose-700">{block.error ?? "This paragraph could not be refined."}</p>
      ) : parts ? (
        <div className={`prose-academic ${block.kind === "list" ? "whitespace-pre-line" : ""} ${block.useOriginal ? "opacity-50" : ""}`}>
          {parts.map((p, i) =>
            p.type === "removed" ? null : p.type === "added" ? (
              <ins key={i} className="diff-add">
                {p.value}
              </ins>
            ) : (
              <span key={i}>{p.value}</span>
            ),
          )}
        </div>
      ) : (
        <Text text={block.original} kind={block.kind} />
      )}
    </div>
  );

  const inline = parts ? (
    <div className={`prose-academic ${block.kind === "list" ? "whitespace-pre-line" : ""}`}>
      {parts.map((p, i) =>
        p.type === "added" ? (
          <ins key={i} className="diff-add">
            {p.value}
          </ins>
        ) : p.type === "removed" ? (
          <del key={i} className="diff-del">
            {p.value}
          </del>
        ) : (
          <span key={i}>{p.value}</span>
        ),
      )}
    </div>
  ) : (
    refined
  );

  return (
    <article
      className={`rounded-xl border bg-white shadow-sm transition ${
        block.status === "error" ? "border-rose-200" : busy ? "border-navy-600/40" : "border-ink-200"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-ink-100 px-4 py-2">
        <div className="flex items-center gap-3 text-xs text-ink-500">
          <span className="font-semibold text-ink-700">¶ {index}</span>
          {hasResult && <span title="Share of original words changed">{Math.round(ratio * 100)}% reworded</span>}
          {STATUS_LABEL[block.status] && (
            <span className={block.status === "error" ? "text-rose-700" : "animate-pulse-soft text-navy-600"}>
              {STATUS_LABEL[block.status]}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {hasResult && (
            <>
              <button
                type="button"
                onClick={async () => {
                  await navigator.clipboard.writeText(finalText(block));
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1200);
                }}
                className="rounded px-2 py-1 text-xs text-ink-500 hover:bg-ink-50 hover:text-ink-900"
              >
                {copied ? "Copied" : "Copy"}
              </button>
              <button
                type="button"
                onClick={onToggleOriginal}
                className="rounded px-2 py-1 text-xs text-ink-500 hover:bg-ink-50 hover:text-ink-900"
              >
                {block.useOriginal ? "Use refined" : "Keep original"}
              </button>
            </>
          )}
          <button
            type="button"
            onClick={onRegenerate}
            disabled={!canRegenerate || busy}
            className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-navy-700 hover:bg-navy-700/5 disabled:cursor-not-allowed disabled:opacity-40"
            title="Rewrite this paragraph again with the current intensity"
          >
            <svg aria-hidden viewBox="0 0 20 20" className={`h-3.5 w-3.5 fill-current ${block.status === "regenerating" ? "animate-spin" : ""}`}>
              <path d="M10 3a7 7 0 0 1 6.3 4H14v2h5V4h-2v1.7A9 9 0 1 0 19 10h-2a7 7 0 1 1-7-7Z" />
            </svg>
            Regenerate
          </button>
        </div>
      </div>

      <div className="px-4 py-3">
        {viewMode === "side" ? (
          <div className="grid gap-5 lg:grid-cols-2">
            {original}
            <div className="lg:border-l lg:border-ink-100 lg:pl-5">{refined}</div>
          </div>
        ) : (
          inline
        )}
      </div>

      {(block.warnings.length > 0 || (block.status === "error" && hasResult)) && (
        <div className="rounded-b-xl border-t border-amber-100 bg-amber-50 px-4 py-2 text-xs text-amber-900">
          {block.warnings.map((w) => (
            <p key={w}>{w}</p>
          ))}
          {block.status === "error" && hasResult && <p>{block.error}</p>}
        </div>
      )}
    </article>
  );
}
