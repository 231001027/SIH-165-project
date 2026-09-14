import { Fragment, useMemo, useState } from "react";

function densityColor(density) {
  if (density == null) return "bg-surface-muted";
  if (density >= 0.66) return "bg-risk-high text-white";
  if (density >= 0.45) return "bg-risk-high/60 text-white";
  if (density >= 0.28) return "bg-risk-medium/70 text-ink-950";
  if (density >= 0.12) return "bg-risk-medium/30 text-ink_text-primary";
  if (density > 0) return "bg-risk-nonsif/20 text-ink_text-primary";
  return "bg-surface-muted text-ink_text-muted";
}

/**
 * Site x Activity SIF-precursor density heatmap (blueprint Part 6.1). `matrix`
 * is the flat list from GET /api/dashboard/heatmap -- pivoted here into a
 * sites x activities grid, one cell per combination that actually has data.
 */
export default function SiteActivityHeatmap({ matrix }) {
  const [hovered, setHovered] = useState(null);

  const { sites, activities, cellByKey } = useMemo(() => {
    const siteSet = [];
    const activitySet = [];
    const byKey = {};
    for (const row of matrix) {
      if (!siteSet.includes(row.site)) siteSet.push(row.site);
      if (!activitySet.includes(row.activity)) activitySet.push(row.activity);
      byKey[`${row.site}__${row.activity}`] = row;
    }
    return { sites: siteSet, activities: activitySet, cellByKey: byKey };
  }, [matrix]);

  if (matrix.length === 0) {
    return <p className="py-10 text-center text-sm text-ink_text-muted">No site/activity data yet.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <div className="inline-grid gap-1" style={{ gridTemplateColumns: `140px repeat(${activities.length}, 84px)` }}>
        <div />
        {activities.map((a) => (
          <div key={a} className="flex items-end justify-center px-1 pb-1 text-center text-[10px] font-semibold leading-tight text-ink_text-secondary">
            {a}
          </div>
        ))}
        {sites.map((site) => (
          <Fragment key={site}>
            <div className="flex items-center pr-2 text-[11.5px] font-bold text-ink_text-primary">
              {site}
            </div>
            {activities.map((activity) => {
              const cell = cellByKey[`${site}__${activity}`];
              const key = `${site}__${activity}`;
              return (
                <button
                  key={key}
                  onMouseEnter={() => setHovered(cell ? key : null)}
                  onMouseLeave={() => setHovered(null)}
                  disabled={!cell}
                  className={`relative h-11 rounded-md text-[11px] font-bold tabular-nums transition ${
                    cell ? densityColor(cell.density) : "bg-surface"
                  } ${cell ? "hover:ring-2 hover:ring-ink-700 hover:ring-offset-1" : "cursor-default"}`}
                >
                  {cell ? `${Math.round(cell.density * 100)}%` : ""}
                  {hovered === key && cell && (
                    <div className="absolute left-1/2 top-full z-10 mt-1.5 w-44 -translate-x-1/2 rounded-lg border border-line bg-ink-900 px-2.5 py-2 text-left text-[11px] font-medium leading-snug text-white shadow-raised">
                      <p className="font-bold">{cell.site}</p>
                      <p className="text-white/70">{cell.activity}</p>
                      <p className="mt-1">
                        {cell.sif_positive_reports} / {cell.total_reports} reports SIF-positive
                      </p>
                    </div>
                  )}
                </button>
              );
            })}
          </Fragment>
        ))}
      </div>
      <div className="mt-3 flex items-center gap-2 text-[10.5px] text-ink_text-muted">
        <span>Lower density</span>
        <span className="h-2.5 w-6 rounded-sm bg-risk-nonsif/20" />
        <span className="h-2.5 w-6 rounded-sm bg-risk-medium/30" />
        <span className="h-2.5 w-6 rounded-sm bg-risk-medium/70" />
        <span className="h-2.5 w-6 rounded-sm bg-risk-high/60" />
        <span className="h-2.5 w-6 rounded-sm bg-risk-high" />
        <span>Higher density</span>
      </div>
    </div>
  );
}
