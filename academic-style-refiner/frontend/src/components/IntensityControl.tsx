import type { Intensity } from "../lib/api";

const OPTIONS: { value: Intensity; label: string; hint: string }[] = [
  { value: "light", label: "Light", hint: "Fix repetition and formulaic phrasing; keep structure." },
  { value: "moderate", label: "Moderate", hint: "Rephrase most sentences; adjust rhythm and clause order." },
  { value: "strong", label: "Strong", hint: "Recompose paragraphs thoroughly; all claims kept intact." },
];

export function IntensityControl({
  value,
  onChange,
  disabled,
}: {
  value: Intensity;
  onChange: (v: Intensity) => void;
  disabled?: boolean;
}) {
  const active = OPTIONS.find((o) => o.value === value)!;
  return (
    <fieldset disabled={disabled} className="min-w-0">
      <legend className="mb-1.5 text-xs font-medium uppercase tracking-wide text-ink-500">Refinement intensity</legend>
      <div role="radiogroup" className="inline-flex rounded-lg border border-ink-200 bg-ink-100 p-0.5">
        {OPTIONS.map((o) => (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={value === o.value}
            onClick={() => onChange(o.value)}
            className={`rounded-md px-3.5 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed ${
              value === o.value ? "bg-white text-navy-700 shadow-sm" : "text-ink-700 hover:text-ink-900"
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>
      <p className="mt-1.5 text-xs text-ink-500">{active.hint}</p>
    </fieldset>
  );
}
