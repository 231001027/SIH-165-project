import { ReferenceIncidentBadge, SifBadge } from "./Badges";

function highlightText(text, spans) {
  if (!text) return null;
  const needles = (spans || []).filter(Boolean).sort((a, b) => b.length - a.length);
  if (!needles.length) return <span>{text}</span>;

  const lower = text.toLowerCase();
  const marks = [];
  for (const span of needles) {
    const idx = lower.indexOf(span.toLowerCase());
    if (idx >= 0) marks.push([idx, idx + span.length]);
  }
  if (!marks.length) return <span>{text}</span>;

  marks.sort((a, b) => a[0] - b[0]);
  const merged = [];
  for (const [s, e] of marks) {
    if (!merged.length || s > merged[merged.length - 1][1]) merged.push([s, e]);
    else merged[merged.length - 1][1] = Math.max(merged[merged.length - 1][1], e);
  }

  const parts = [];
  let cursor = 0;
  merged.forEach(([s, e], i) => {
    if (cursor < s) parts.push(<span key={`t${i}`}>{text.slice(cursor, s)}</span>);
    parts.push(
      <mark key={`m${i}`} className="rounded bg-amber-200/80 px-0.5 text-ink_text-primary">
        {text.slice(s, e)}
      </mark>
    );
    cursor = e;
  });
  if (cursor < text.length) parts.push(<span key="tail">{text.slice(cursor)}</span>);
  return <>{parts}</>;
}

export default function PrecursorComparisonView({ comparison, onClose }) {
  if (!comparison) return null;

  return (
    <div className="mt-3 space-y-3 rounded-xl border border-accent-200 bg-white p-3.5">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-[12px] font-extrabold uppercase tracking-wide text-accent-700">Cited precursor comparison</p>
          <p className="mt-0.5 text-[12px] text-ink_text-secondary">
            {comparison.match_title || `Report #${comparison.match_report_id}`}
            {comparison.match_source === "PUBLIC_CORPUS" && (
              <span className="ml-2 inline-block align-middle"><ReferenceIncidentBadge /></span>
            )}
          </p>
          {comparison.citation_url && (
            <a href={comparison.citation_url} target="_blank" rel="noreferrer" className="text-[11px] font-semibold text-accent-700 hover:underline">
              {comparison.citation_label || "Open citation"}
            </a>
          )}
        </div>
        <button type="button" onClick={onClose} className="text-[12px] font-bold text-ink_text-muted hover:text-ink_text-primary">Close</button>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-line bg-surface-muted/40 p-2.5">
          <p className="mb-1.5 text-[11px] font-bold uppercase text-ink_text-muted">This report</p>
          <p className="text-[12.5px] leading-relaxed text-ink_text-primary">
            {highlightText(comparison.query_narrative, comparison.query_highlights)}
          </p>
        </div>
        <div className="rounded-lg border border-line bg-surface-muted/40 p-2.5">
          <p className="mb-1.5 text-[11px] font-bold uppercase text-ink_text-muted">Retrieved incident</p>
          <p className="text-[12.5px] leading-relaxed text-ink_text-primary">
            {highlightText(comparison.match_narrative, comparison.match_highlights)}
          </p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-left text-[12px]">
          <thead>
            <tr className="border-b border-line text-[11px] uppercase tracking-wide text-ink_text-muted">
              <th className="py-1.5 pr-2">Condition</th>
              <th className="py-1.5 pr-2">Shared?</th>
              <th className="py-1.5 pr-2">Query evidence</th>
              <th className="py-1.5">Match evidence</th>
            </tr>
          </thead>
          <tbody>
            {(comparison.fields || []).map((f) => (
              <tr key={f.field} className="border-b border-line/70 align-top">
                <td className="py-2 pr-2 font-semibold text-ink_text-primary">
                  {f.field}
                  <div className="mt-0.5 text-[11px] font-normal text-ink_text-secondary">{f.reason}</div>
                </td>
                <td className="py-2 pr-2">
                  <span className={`rounded-md border px-1.5 py-0.5 text-[10.5px] font-bold ${f.shared ? "border-risk-nonsif/30 bg-risk-nonsif/10 text-risk-nonsif" : "border-line bg-surface-muted text-ink_text-muted"}`}>
                    {f.shared ? "SHARED" : "DIFFERENT"}
                  </span>
                </td>
                <td className="py-2 pr-2 italic text-ink_text-secondary">{f.query_evidence || "—"}</td>
                <td className="py-2 italic text-ink_text-secondary">{f.match_evidence || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
