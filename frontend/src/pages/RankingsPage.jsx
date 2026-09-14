import { useEffect, useState } from "react";
import api, { extractErrorMessage } from "../services/api";
import PageHeader from "../components/PageHeader";
import { LoadingState, ErrorState } from "../components/StateViews";
import { Card, CardHeader } from "../components/ui";
import SiteActivityHeatmap from "../components/SiteActivityHeatmap";
import { IconRank, IconMapPin, IconLayers } from "../components/icons";

function densityTone(density) {
  if (density >= 0.5) return "bg-risk-high/10 text-risk-high";
  if (density >= 0.25) return "bg-risk-medium/10 text-risk-medium";
  return "bg-risk-nonsif/10 text-risk-nonsif";
}

function RankingTable({ title, icon, ranking, caveat }) {
  return (
    <Card>
      <CardHeader title={title} icon={icon} />
      <p className="mb-3.5 -mt-2 text-[11.5px] italic text-ink_text-muted">{caveat}</p>
      {ranking.length === 0 ? (
        <p className="py-8 text-center text-sm text-ink_text-muted">No data yet.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-[10.5px] font-bold uppercase tracking-wide text-ink_text-muted">
              <th className="py-2">#</th>
              <th className="py-2">Name</th>
              <th className="py-2 text-right">SIF Density</th>
              <th className="py-2 text-right">SIF+ / Total</th>
              <th className="py-2 text-right">HIGH</th>
            </tr>
          </thead>
          <tbody>
            {ranking.map((r, i) => (
              <tr key={r.name} className="border-b border-line/70">
                <td className="py-2.5 text-ink_text-muted">{i + 1}</td>
                <td className="py-2.5 font-bold text-ink_text-primary">{r.name}</td>
                <td className="py-2.5 text-right">
                  <span className={`rounded-md px-2 py-0.5 text-xs font-bold ${densityTone(r.density)}`}>
                    {(r.density * 100).toFixed(0)}%
                  </span>
                </td>
                <td className="py-2.5 text-right tabular-nums text-ink_text-secondary">{r.sif_positive_reports} / {r.total_reports}</td>
                <td className="py-2.5 text-right tabular-nums text-ink_text-secondary">{r.high_reports}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

export default function RankingsPage() {
  const [sites, setSites] = useState(null);
  const [activities, setActivities] = useState(null);
  const [heatmap, setHeatmap] = useState(null);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      const [s, a, h] = await Promise.all([
        api.get("/api/dashboard/sites"),
        api.get("/api/dashboard/activities"),
        api.get("/api/dashboard/heatmap"),
      ]);
      setSites(s.data);
      setActivities(a.data);
      setHeatmap(h.data);
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to load rankings."));
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!sites || !activities || !heatmap) return <LoadingState label="Loading rankings..." />;

  return (
    <div>
      <PageHeader
        eyebrow="Pattern intelligence"
        title="Site & Activity SIF-Precursor Ranking"
        description="Ranked by SIF-precursor density (SIF-potential reports / total reports for that site or activity), with raw counts shown alongside so HSE can sanity-check both."
      />
      <div className="space-y-5">
        <Card>
          <CardHeader title="Site x Activity Risk Heatmap" icon={<IconRank className="h-4 w-4" />} />
          <p className="mb-3.5 -mt-2 text-[11.5px] italic text-ink_text-muted">{heatmap.caveat}</p>
          <SiteActivityHeatmap matrix={heatmap.matrix} />
        </Card>
        <RankingTable title="Sites Ranked by SIF-Precursor Density" icon={<IconMapPin className="h-4 w-4" />} ranking={sites.ranking} caveat={sites.caveat} />
        <RankingTable title="Activities Ranked by SIF-Precursor Density" icon={<IconLayers className="h-4 w-4" />} ranking={activities.ranking} caveat={activities.caveat} />
      </div>
    </div>
  );
}
