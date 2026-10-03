import type { Metrics } from "../lib/api";

type Better = "higher" | "lower" | "neutral";

const ROWS: { key: keyof Metrics; label: string; help: string; better: Better; pct?: boolean }[] = [
  { key: "words", label: "Words", help: "Total word count.", better: "neutral" },
  {
    key: "flesch_reading_ease",
    label: "Reading ease",
    help: "Flesch Reading Ease (0-100). Higher is easier to read; academic prose usually sits between 10 and 50.",
    better: "higher",
  },
  {
    key: "flesch_kincaid_grade",
    label: "Grade level",
    help: "Flesch-Kincaid grade level. Lower means less effort for the reader.",
    better: "lower",
  },
  {
    key: "mtld",
    label: "Lexical diversity (MTLD)",
    help: "Measure of Textual Lexical Diversity. Higher means a richer, less repetitive vocabulary; robust to text length.",
    better: "higher",
  },
  {
    key: "mattr",
    label: "Moving type-token ratio",
    help: "Average share of distinct words in every 50-word window.",
    better: "higher",
  },
  {
    key: "mean_sentence_length",
    label: "Mean sentence length",
    help: "Average words per sentence.",
    better: "neutral",
  },
  {
    key: "sentence_length_variation",
    label: "Sentence-length variation",
    help: "Standard deviation divided by the mean. Higher means a more varied rhythm of short and long sentences.",
    better: "higher",
  },
  {
    key: "opening_variety",
    label: "Sentence-opening variety",
    help: "Share of sentences whose first word is not repeated as another sentence's first word.",
    better: "higher",
    pct: true,
  },
];

function fmt(value: number, pct?: boolean) {
  if (pct) return `${Math.round(value * 100)}%`;
  return Number.isInteger(value) ? value.toLocaleString() : value.toFixed(value < 1 ? 3 : 1);
}

function Delta({ before, after, better }: { before: number; after: number; better: Better }) {
  const diff = after - before;
  if (Math.abs(diff) < 1e-9) return <span className="text-ink-300">±0</span>;
  const good = better === "neutral" ? null : (diff > 0) === (better === "higher");
  const color = good === null ? "text-ink-500" : good ? "text-emerald-700" : "text-rose-700";
  const rel = before ? ` (${diff > 0 ? "+" : ""}${Math.round((diff / Math.abs(before)) * 100)}%)` : "";
  return (
    <span className={`whitespace-nowrap tabular-nums ${color}`}>
      {diff > 0 ? "▲" : "▼"}
      {rel}
    </span>
  );
}

function Histogram({ before, after }: { before: Metrics; after: Metrics }) {
  const buckets = Object.keys(before.sentence_length_histogram);
  const max = Math.max(1, ...buckets.flatMap((b) => [before.sentence_length_histogram[b], after.sentence_length_histogram[b] ?? 0]));
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-xs text-ink-500">
        <span>Sentence lengths (words)</span>
        <span className="flex gap-3">
          <span className="flex items-center gap-1">
            <i className="h-2 w-2 rounded-sm bg-ink-300" /> Before
          </span>
          <span className="flex items-center gap-1">
            <i className="h-2 w-2 rounded-sm bg-navy-600" /> After
          </span>
        </span>
      </div>
      <div className="flex h-24 items-end gap-3">
        {buckets.map((b) => (
          <div key={b} className="flex flex-1 flex-col items-center gap-1">
            <div className="flex h-20 w-full items-end justify-center gap-0.5">
              {[
                [before.sentence_length_histogram[b], "bg-ink-300"],
                [after.sentence_length_histogram[b] ?? 0, "bg-navy-600"],
              ].map(([n, color], i) => (
                <div
                  key={i}
                  title={`${i ? "After" : "Before"}: ${n} sentences`}
                  className={`w-1/2 max-w-4 rounded-t-sm ${color}`}
                  style={{ height: `${((n as number) / max) * 100}%`, minHeight: (n as number) ? 2 : 0 }}
                />
              ))}
            </div>
            <span className="text-[10px] text-ink-500">{b}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function MetricsPanel({ before, after }: { before: Metrics; after: Metrics | null }) {
  return (
    <section className="rounded-xl border border-ink-200 bg-white shadow-sm">
      <h2 className="border-b border-ink-100 px-4 py-3 text-sm font-semibold text-ink-900">Style metrics</h2>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-ink-500">
            <th className="px-4 pt-2 font-medium">Metric</th>
            <th className="px-2 pt-2 text-right font-medium">Before</th>
            <th className="px-2 pt-2 text-right font-medium">After</th>
            <th className="px-4 pt-2 text-right font-medium">Change</th>
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row) => {
            const b = before[row.key] as number;
            const a = after ? (after[row.key] as number) : null;
            return (
              <tr key={row.key} className="border-t border-ink-100 first:border-t-0">
                <td className="px-4 py-1.5 text-ink-700">
                  <abbr title={row.help} className="cursor-help no-underline decoration-dotted hover:underline">
                    {row.label}
                  </abbr>
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums text-ink-500">{fmt(b, row.pct)}</td>
                <td className="px-2 py-1.5 text-right font-medium tabular-nums text-ink-900">{a === null ? "…" : fmt(a, row.pct)}</td>
                <td className="px-4 py-1.5 text-right text-xs">{a !== null && <Delta before={b} after={a} better={row.better} />}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {after && (
        <div className="space-y-4 border-t border-ink-100 px-4 py-4">
          <Histogram before={before} after={after} />
          {(before.repeated_phrases.length > 0 || after.repeated_phrases.length > 0) && (
            <div className="grid grid-cols-2 gap-3 text-xs">
              {[
                ["Repeated phrases before", before.repeated_phrases],
                ["Repeated phrases after", after.repeated_phrases],
              ].map(([label, phrases]) => (
                <div key={label as string}>
                  <p className="mb-1 font-medium text-ink-500">{label as string}</p>
                  {(phrases as [string, number][]).length === 0 ? (
                    <p className="text-ink-300">None repeated 3+ times</p>
                  ) : (
                    <ul className="space-y-0.5">
                      {(phrases as [string, number][]).slice(0, 5).map(([p, n]) => (
                        <li key={p} className="flex justify-between gap-2 text-ink-700">
                          <span className="truncate">“{p}”</span>
                          <span className="tabular-nums text-ink-500">×{n}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
