import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ExportMenu } from "./components/ExportMenu";
import { Header } from "./components/Header";
import { InputPanel } from "./components/InputPanel";
import { IntensityControl } from "./components/IntensityControl";
import { MetricsPanel } from "./components/MetricsPanel";
import { ParagraphCard, type ViewMode } from "./components/ParagraphCard";
import { ProgressPanel } from "./components/ProgressPanel";
import { ResponsibleUse } from "./components/ResponsibleUse";
import { api, type ExportFormat, type Health, type Intensity, type JobEvent, type Metrics } from "./lib/api";
import { countWords } from "./lib/diff";
import { finalText, isRewritable, type UiBlock } from "./types";

type Phase = "input" | "processing" | "results";

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [intensity, setIntensity] = useState<Intensity>("moderate");
  const [phase, setPhase] = useState<Phase>("input");
  const [blocks, setBlocks] = useState<UiBlock[]>([]);
  const [progress, setProgress] = useState({ completed: 0, total: 0 });
  const [metricsBefore, setMetricsBefore] = useState<Metrics | null>(null);
  const [metricsAfter, setMetricsAfter] = useState<Metrics | null>(null);
  const [metricsDirty, setMetricsDirty] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>("side");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const jobRef = useRef<{ id: string; close: () => void } | null>(null);

  const maxWords = health?.max_words ?? 10_000;
  const words = countWords(text);

  useEffect(() => {
    api.health().then(setHealth, () => setError("The server is not reachable. Is the backend running?"));
  }, []);

  const updateBlock = useCallback((id: number, patch: Partial<UiBlock> | ((b: UiBlock) => Partial<UiBlock>)) => {
    setBlocks((prev) => prev.map((b) => (b.id === id ? { ...b, ...(typeof patch === "function" ? patch(b) : patch) } : b)));
  }, []);

  const closeJob = useCallback((deleteOnServer: boolean) => {
    const job = jobRef.current;
    if (!job) return;
    job.close();
    jobRef.current = null;
    // The browser now holds everything it needs; purge the server copy straight away.
    if (deleteOnServer) api.deleteJob(job.id).catch(() => {});
  }, []);

  useEffect(() => () => closeJob(true), [closeJob]);

  const handleEvent = useCallback(
    (e: JobEvent) => {
      switch (e.event) {
        case "progress":
          setProgress(e.data);
          break;
        case "stage":
          updateBlock(e.data.block_id, { status: e.data.stage });
          break;
        case "block":
          updateBlock(e.data.block_id, { refined: e.data.text, warnings: e.data.warnings, status: "done" });
          break;
        case "block_error":
          updateBlock(e.data.block_id, { status: "error", error: e.data.message });
          break;
        case "done":
          if (e.data.metrics_before) setMetricsBefore(e.data.metrics_before);
          if (e.data.metrics_after) setMetricsAfter(e.data.metrics_after);
          if (e.data.status === "failed") {
            setError(e.data.message ?? "No paragraph could be refined. Please try again later.");
          }
          setPhase("results");
          closeJob(true);
          break;
      }
    },
    [closeJob, updateBlock],
  );

  async function start() {
    setError(null);
    setSubmitting(true);
    try {
      const job = await api.createJob(text, intensity);
      setBlocks(
        job.blocks.map((b) => ({
          id: b.id,
          kind: b.kind,
          original: b.text,
          refined: null,
          status: isRewritable(b.kind) ? "queued" : "static",
          warnings: [],
          history: [],
          useOriginal: false,
        })),
      );
      setProgress({ completed: 0, total: job.blocks.filter((b) => isRewritable(b.kind)).length });
      setMetricsBefore(null);
      setMetricsAfter(null);
      setPhase("processing");
      const close = api.subscribe(job.job_id, handleEvent, () => {
        setError("Lost connection to the server while refining. Completed paragraphs are shown below.");
        setPhase("results");
        closeJob(false);
      });
      jobRef.current = { id: job.job_id, close };
      if (!title) {
        const heading = job.blocks.find((b) => b.kind === "heading");
        if (heading) setTitle(heading.text.replace(/^#+\s*/, "").slice(0, 120));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start refinement.");
    } finally {
      setSubmitting(false);
    }
  }

  function cancel() {
    closeJob(true);
    setPhase("input");
    setBlocks([]);
  }

  function startOver() {
    closeJob(true);
    setPhase("input");
    setBlocks([]);
    setMetricsBefore(null);
    setMetricsAfter(null);
    setError(null);
  }

  async function regenerate(index: number) {
    const block = blocks[index];
    const prev = blocks[index - 1];
    const next = blocks[index + 1];
    updateBlock(block.id, { status: "regenerating" });
    try {
      const result = await api.refineParagraph({
        text: block.original,
        intensity,
        context_before: prev ? finalText(prev) : null,
        context_after: next ? next.original : null,
        previous: block.refined,
      });
      updateBlock(block.id, (b) => ({
        refined: result.text,
        warnings: result.warnings,
        history: b.refined ? [...b.history, b.refined] : b.history,
        useOriginal: false,
        status: "done",
        error: undefined,
      }));
      setMetricsDirty(true);
    } catch (e) {
      updateBlock(block.id, { status: "error", error: e instanceof Error ? e.message : "Regeneration failed." });
    }
  }

  // Recompute "after" metrics when the user regenerates or reverts paragraphs.
  const outputText = useMemo(() => blocks.map(finalText).join("\n\n"), [blocks]);
  useEffect(() => {
    if (!metricsDirty || phase !== "results") return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      api.analyze(outputText, controller.signal).then((m) => {
        setMetricsAfter(m);
        setMetricsDirty(false);
      }, () => {});
    }, 600);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [metricsDirty, outputText, phase]);

  async function exportAs(format: ExportFormat) {
    try {
      await api.export(
        format,
        title,
        blocks.map((b) => ({ kind: b.kind, text: finalText(b) })),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed.");
    }
  }

  const activeLabel = useMemo(() => {
    const polishing = blocks.filter((b) => b.status === "polish").length;
    const rewriting = blocks.filter((b) => b.status === "rewrite").length;
    return [rewriting && `${rewriting} in first pass`, polishing && `${polishing} polishing`].filter(Boolean).join(" · ");
  }, [blocks]);

  let paragraphNumber = 0;

  return (
    <div className="min-h-screen">
      <Header health={health} />

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        {error && (
          <div role="alert" className="mb-4 flex items-start justify-between gap-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
            <span>{error}</span>
            <button type="button" onClick={() => setError(null)} className="text-rose-600 hover:text-rose-900" aria-label="Dismiss">
              ✕
            </button>
          </div>
        )}

        {phase === "input" ? (
          <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
            <InputPanel
              text={text}
              onTextChange={setText}
              title={title}
              onTitleChange={setTitle}
              maxWords={maxWords}
              onError={setError}
            />
            <aside className="space-y-4">
              <div className="rounded-xl border border-ink-200 bg-white p-4 shadow-sm">
                <IntensityControl value={intensity} onChange={setIntensity} />
                <button
                  type="button"
                  onClick={start}
                  disabled={!text.trim() || words > maxWords || submitting || !health}
                  className="mt-4 w-full rounded-lg bg-navy-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-navy-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {submitting ? "Starting…" : "Refine document"}
                </button>
              </div>
              <div className="rounded-xl border border-ink-200 bg-white p-4 text-xs leading-relaxed text-ink-700 shadow-sm">
                <p className="mb-2 font-semibold text-ink-900">How it works</p>
                <ol className="list-decimal space-y-1.5 pl-4">
                  <li>Your text is split into paragraphs; headings and the reference list are left untouched.</li>
                  <li>Citations, quotations, URLs and equations are locked so the model cannot alter them.</li>
                  <li>Pass 1 rephrases each paragraph for variety and natural flow at your chosen intensity.</li>
                  <li>Pass 2 checks every claim against the original, then polishes coherence and rhythm.</li>
                  <li>Any rewrite that drops a citation or number is retried, or the original is kept.</li>
                </ol>
              </div>
            </aside>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <h2 className="font-serif text-2xl font-semibold text-ink-900">{title || "Refined document"}</h2>
                <p className="text-sm text-ink-500">
                  {intensity[0].toUpperCase() + intensity.slice(1)} refinement · deletions in red, insertions in green
                </p>
              </div>
              <div className="flex flex-wrap items-end gap-4">
                <div className="inline-flex rounded-lg border border-ink-200 bg-ink-100 p-0.5 text-sm">
                  {(["side", "inline"] as ViewMode[]).map((m) => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => setViewMode(m)}
                      className={`rounded-md px-3 py-1.5 ${viewMode === m ? "bg-white text-navy-700 shadow-sm" : "text-ink-700"}`}
                    >
                      {m === "side" ? "Side by side" : "Inline changes"}
                    </button>
                  ))}
                </div>
                {phase === "results" && <ExportMenu onExport={exportAs} />}
                {phase === "results" && (
                  <button type="button" onClick={startOver} className="rounded-md px-3 py-1.5 text-sm text-ink-500 hover:text-ink-900">
                    Start over
                  </button>
                )}
              </div>
            </div>

            {phase === "processing" && (
              <ProgressPanel completed={progress.completed} total={progress.total} activeLabel={activeLabel} onCancel={cancel} />
            )}

            <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
              <div className="space-y-3">
                {blocks.map((block, i) => (
                  <ParagraphCard
                    key={block.id}
                    block={block}
                    index={isRewritable(block.kind) ? ++paragraphNumber : 0}
                    viewMode={viewMode}
                    canRegenerate={phase === "results"}
                    onRegenerate={() => regenerate(i)}
                    onToggleOriginal={() => {
                      updateBlock(block.id, (b) => ({ useOriginal: !b.useOriginal }));
                      setMetricsDirty(true);
                    }}
                  />
                ))}
              </div>
              <aside className="space-y-4 xl:sticky xl:top-4 xl:self-start">
                {phase === "results" && (
                  <div className="rounded-xl border border-ink-200 bg-white p-4 shadow-sm">
                    <IntensityControl value={intensity} onChange={setIntensity} />
                    <p className="mt-2 text-xs text-ink-500">Used when you regenerate a paragraph.</p>
                  </div>
                )}
                {metricsBefore ? (
                  <MetricsPanel before={metricsBefore} after={metricsDirty ? null : metricsAfter} />
                ) : (
                  <div className="rounded-xl border border-ink-200 bg-white p-4 text-sm text-ink-500 shadow-sm">
                    Metrics appear when refinement finishes.
                  </div>
                )}
              </aside>
            </div>
          </div>
        )}
      </main>

      <ResponsibleUse />
    </div>
  );
}
