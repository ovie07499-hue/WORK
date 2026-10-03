export type Intensity = "light" | "moderate" | "strong";
export type BlockKind = "heading" | "paragraph" | "list" | "reference";
export type ExportFormat = "txt" | "docx" | "pdf";

export interface Metrics {
  words: number;
  sentences: number;
  paragraphs: number;
  reading_minutes: number;
  flesch_reading_ease: number;
  flesch_kincaid_grade: number;
  type_token_ratio: number;
  mattr: number;
  mtld: number;
  mean_sentence_length: number;
  sentence_length_sd: number;
  sentence_length_variation: number;
  sentence_length_histogram: Record<string, number>;
  opening_variety: number;
  repeated_phrases: [string, number][];
}

export interface SourceBlock {
  id: number;
  kind: BlockKind;
  text: string;
}

export interface Health {
  status: string;
  model: string;
  mock: boolean;
  max_words: number;
}

export type JobEvent =
  | { event: "progress"; data: { completed: number; total: number } }
  | { event: "stage"; data: { block_id: number; stage: "rewrite" | "polish" } }
  | { event: "block"; data: { block_id: number; text: string; warnings: string[] } }
  | { event: "block_error"; data: { block_id: number; message: string } }
  | {
      event: "done";
      data: { status: string; metrics_before?: Metrics; metrics_after?: Metrics; message?: string };
    };

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError("Could not reach the server. Check your connection and try again.", 0);
  }
  if (!res.ok) {
    let message = `Request failed (${res.status}).`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(message, res.status);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => request<Health>("/api/health"),

  analyze: (text: string, signal?: AbortSignal) => request<Metrics>("/api/analyze", { ...json({ text }), signal }),

  extract: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ filename: string; text: string; words: number }>("/api/extract", { method: "POST", body: form });
  },

  createJob: (text: string, intensity: Intensity) =>
    request<{ job_id: string; blocks: SourceBlock[] }>("/api/jobs", json({ text, intensity })),

  deleteJob: (jobId: string) => request<void>(`/api/jobs/${jobId}`, { method: "DELETE" }),

  refineParagraph: (body: {
    text: string;
    intensity: Intensity;
    context_before?: string | null;
    context_after?: string | null;
    previous?: string | null;
  }) => request<{ text: string; warnings: string[] }>("/api/refine/paragraph", json(body)),

  async export(format: ExportFormat, title: string, blocks: { kind: BlockKind; text: string }[]) {
    const res = await fetch("/api/export", json({ format, title, blocks }));
    if (!res.ok) throw new ApiError(`Export failed (${res.status}).`, res.status);
    const blob = await res.blob();
    const match = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "");
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = match?.[1] ?? `refined-document.${format}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },

  /** Subscribe to a job's progress stream. Returns a function that closes the stream. */
  subscribe(jobId: string, onEvent: (e: JobEvent) => void, onError: () => void): () => void {
    const source = new EventSource(`/api/jobs/${jobId}/events`);
    const kinds: JobEvent["event"][] = ["progress", "stage", "block", "block_error", "done"];
    for (const kind of kinds) {
      source.addEventListener(kind, (msg) => {
        const event = { event: kind, data: JSON.parse((msg as MessageEvent).data) } as JobEvent;
        onEvent(event);
        if (kind === "done") source.close();
      });
    }
    source.onerror = () => {
      // EventSource reconnects on its own while the server is reachable; give up only once it is closed.
      if (source.readyState === EventSource.CLOSED) onError();
    };
    return () => source.close();
  },
};
