const ACCENTS = {
  ink: { bg: "bg-ink-900/[0.06]", text: "text-ink-900", ring: "ring-ink-900/10" },
  accent: { bg: "bg-accent-100", text: "text-accent-700", ring: "ring-accent-200" },
  high: { bg: "bg-risk-high/10", text: "text-risk-high", ring: "ring-risk-high/15" },
  medium: { bg: "bg-risk-medium/10", text: "text-risk-medium", ring: "ring-risk-medium/15" },
  nonsif: { bg: "bg-risk-nonsif/10", text: "text-risk-nonsif", ring: "ring-risk-nonsif/15" },
  review: { bg: "bg-risk-review/10", text: "text-risk-review", ring: "ring-risk-review/15" },
};

export default function KpiCard({ label, value, accent = "ink", sub, icon }) {
  const a = ACCENTS[accent] || ACCENTS.ink;
  return (
    <div className="group relative overflow-hidden rounded-2xl border border-line bg-surface-raised p-4 shadow-card transition hover:-translate-y-0.5 hover:shadow-raised">
      <div className="flex items-start justify-between">
        <p className="text-[11px] font-bold uppercase tracking-wide text-ink_text-muted">{label}</p>
        {icon && (
          <span className={`flex h-8 w-8 items-center justify-center rounded-lg ${a.bg} ${a.text}`}>
            {icon}
          </span>
        )}
      </div>
      <p className="mt-2 text-[28px] font-extrabold leading-none tabular-nums text-ink_text-primary">
        {value}
      </p>
      {sub && <p className="mt-1.5 text-[11.5px] leading-snug text-ink_text-muted">{sub}</p>}
      <div className={`pointer-events-none absolute -right-6 -top-6 h-20 w-20 rounded-full ${a.bg} opacity-60 blur-xl`} />
    </div>
  );
}
