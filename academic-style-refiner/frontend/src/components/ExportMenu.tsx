import { useState } from "react";
import type { ExportFormat } from "../lib/api";

export function ExportMenu({ onExport }: { onExport: (format: ExportFormat) => Promise<void> }) {
  const [busy, setBusy] = useState<ExportFormat | null>(null);
  const formats: ExportFormat[] = ["docx", "pdf", "txt"];
  return (
    <div className="flex items-center gap-1.5">
      <span className="mr-1 text-xs font-medium uppercase tracking-wide text-ink-500">Export</span>
      {formats.map((f) => (
        <button
          key={f}
          type="button"
          disabled={busy !== null}
          onClick={async () => {
            setBusy(f);
            try {
              await onExport(f);
            } finally {
              setBusy(null);
            }
          }}
          className="rounded-md border border-ink-200 bg-white px-3 py-1.5 text-sm font-medium text-ink-700 hover:border-navy-600 hover:text-navy-700 disabled:opacity-50"
        >
          {busy === f ? "…" : `.${f}`}
        </button>
      ))}
    </div>
  );
}
