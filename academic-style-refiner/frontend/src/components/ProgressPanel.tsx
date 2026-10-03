export function ProgressPanel({
  completed,
  total,
  activeLabel,
  onCancel,
}: {
  completed: number;
  total: number;
  activeLabel: string;
  onCancel: () => void;
}) {
  const pct = total ? Math.round((completed / total) * 100) : 0;
  return (
    <div className="rounded-xl border border-ink-200 bg-white p-4 shadow-sm" role="status" aria-live="polite">
      <div className="mb-2 flex items-center justify-between gap-4 text-sm">
        <span className="font-medium text-ink-900">
          Refining paragraph {Math.min(completed + 1, total)} of {total}
          <span className="ml-2 font-normal text-ink-500">{activeLabel}</span>
        </span>
        <div className="flex items-center gap-4">
          <span className="tabular-nums text-ink-500">{pct}%</span>
          <button type="button" onClick={onCancel} className="text-sm text-ink-500 underline-offset-2 hover:text-rose-700 hover:underline">
            Cancel
          </button>
        </div>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-ink-100">
        <div className="h-full rounded-full bg-navy-600 transition-[width] duration-500" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
