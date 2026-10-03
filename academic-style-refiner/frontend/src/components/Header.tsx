import type { Health } from "../lib/api";

export function Header({ health }: { health: Health | null }) {
  return (
    <header className="border-b border-ink-200 bg-white">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-navy-700 font-serif text-lg text-white">A</div>
          <div>
            <h1 className="font-serif text-xl font-semibold tracking-tight text-ink-900">Academic Style Refiner</h1>
            <p className="text-xs text-ink-500">Clearer flow, richer variety, same meaning.</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-emerald-800">
            <svg aria-hidden viewBox="0 0 20 20" className="h-3.5 w-3.5 fill-current">
              <path d="M10 1.5 3 4.5v5c0 4.3 3 8 7 9 4-1 7-4.7 7-9v-5l-7-3Zm-1 12.1L5.6 10.2l1.4-1.4 2 2 4-4 1.4 1.4-5.4 5.4Z" />
            </svg>
            Processed in memory only, never stored
          </span>
          {health?.mock && (
            <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-amber-800">
              Demo mode: offline mock rewriter
            </span>
          )}
        </div>
      </div>
    </header>
  );
}
