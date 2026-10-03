import { useEffect, useRef, useState } from "react";
import { api, type Metrics } from "../lib/api";
import { countWords } from "../lib/diff";

interface Props {
  text: string;
  onTextChange: (text: string) => void;
  title: string;
  onTitleChange: (title: string) => void;
  maxWords: number;
  onError: (message: string) => void;
}

export function InputPanel({ text, onTextChange, title, onTitleChange, maxWords, onError }: Props) {
  const [preview, setPreview] = useState<Metrics | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const words = countWords(text);
  const over = words > maxWords;

  // Debounced readability preview.
  useEffect(() => {
    if (!text.trim() || over) {
      setPreview(null);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      api.analyze(text, controller.signal).then(setPreview, () => {});
    }, 500);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [text, over]);

  async function handleFile(file: File) {
    setUploading(true);
    try {
      const result = await api.extract(file);
      onTextChange(result.text);
      if (!title) onTitleChange(file.name.replace(/\.[^.]+$/, ""));
    } catch (e) {
      onError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  return (
    <section className="rounded-xl border border-ink-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center gap-3 border-b border-ink-100 px-4 py-3">
        <input
          value={title}
          onChange={(e) => onTitleChange(e.target.value)}
          placeholder="Document title (optional, used for exports)"
          maxLength={200}
          className="min-w-0 flex-1 rounded-md border border-transparent px-2 py-1 font-serif text-lg text-ink-900 placeholder:text-ink-300 hover:border-ink-200 focus:border-navy-600 focus:outline-none"
        />
        <input
          ref={fileInput}
          type="file"
          accept=".txt,.md,.docx"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
        <button
          type="button"
          onClick={() => fileInput.current?.click()}
          disabled={uploading}
          className="inline-flex items-center gap-2 rounded-md border border-ink-200 px-3 py-1.5 text-sm text-ink-700 hover:bg-ink-50 disabled:opacity-60"
        >
          <svg aria-hidden viewBox="0 0 20 20" className="h-4 w-4 fill-current">
            <path d="M10 2 5.5 6.5l1.4 1.4L9 5.8V13h2V5.8l2.1 2.1 1.4-1.4L10 2ZM4 14v2h12v-2h2v4H2v-4h2Z" />
          </svg>
          {uploading ? "Reading file…" : "Upload .txt / .docx"}
        </button>
        {text && (
          <button type="button" onClick={() => onTextChange("")} className="text-sm text-ink-500 hover:text-ink-900">
            Clear
          </button>
        )}
      </div>

      <div
        className={`relative ${dragging ? "ring-2 ring-navy-600 ring-inset" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const file = e.dataTransfer.files?.[0];
          if (file) handleFile(file);
        }}
      >
        <textarea
          value={text}
          onChange={(e) => onTextChange(e.target.value)}
          placeholder={
            "Paste your report here, or drop a .txt / .docx file.\n\nSeparate paragraphs with a blank line. Headings, citations, numbers, quotations and the reference list are preserved exactly."
          }
          spellCheck
          className="prose-academic block h-[52vh] min-h-72 w-full resize-y rounded-b-xl px-5 py-4 placeholder:font-sans placeholder:text-sm placeholder:text-ink-300 focus:outline-none"
        />
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-ink-100 px-4 py-2.5 text-xs text-ink-500">
        <span className={over ? "font-semibold text-rose-600" : "font-medium text-ink-700"}>
          {words.toLocaleString()} / {maxWords.toLocaleString()} words
        </span>
        {preview && (
          <>
            <span>{preview.paragraphs} paragraphs</span>
            <span>{preview.sentences} sentences</span>
            <span title="Flesch Reading Ease: higher is easier; academic prose is typically 10-50.">
              Reading ease {preview.flesch_reading_ease}
            </span>
            <span title="Flesch-Kincaid grade level">Grade {preview.flesch_kincaid_grade}</span>
            <span title="Measure of Textual Lexical Diversity">MTLD {preview.mtld}</span>
            <span>~{Math.max(1, Math.round(preview.reading_minutes))} min read</span>
          </>
        )}
        {over && <span className="text-rose-600">Please shorten the text or split it into parts.</span>}
      </div>
    </section>
  );
}
