import { useEffect, useState } from "react";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  BarChart, Bar, PieChart, Pie, Cell,
} from "recharts";
import { Link } from "react-router-dom";
import api, { extractErrorMessage } from "../services/api";
import PageHeader from "../components/PageHeader";
import KpiCard from "../components/KpiCard";
import { Card, CardHeader } from "../components/ui";
import { LoadingState, ErrorState } from "../components/StateViews";
import { SyntheticBadge } from "../components/Badges";
import SiteActivityHeatmap from "../components/SiteActivityHeatmap";
import {
  IconList, IconFlame, IconBolt, IconEval, IconTrend, IconRank, IconAlertTriangle, IconArrowUpRight, IconCheckShield,
} from "../components/icons";

const SIF_COLORS = { HIGH: "#e0264f", MEDIUM: "#f2932c", LOW: "#d4a017", NON_SIF: "#189a6b", REVIEW: "#7c5cf0" };
const CHART_GRID = "#eceef6";
const TICK = { fontSize: 11, fill: "#8b93aa" };

function ChartCard({ title, subtitle, icon, children, className = "" }) {
  return (
    <Card className={className}>
      <CardHeader title={title} subtitle={subtitle} icon={icon} />
      {children}
    </Card>
  );
}

export default function DashboardPage() {
  const [summary, setSummary] = useState(null);
  const [trends, setTrends] = useState(null);
  const [lsr, setLsr] = useState([]);
  const [barriers, setBarriers] = useState([]);
  const [sites, setSites] = useState([]);
  const [heatmap, setHeatmap] = useState([]);
  const [lsrBySite, setLsrBySite] = useState(null);
  const [responseTime, setResponseTime] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [s, t, l, b, sitesResp, heatmapResp, lsrSiteResp, rt] = await Promise.all([
        api.get("/api/dashboard/summary"),
        api.get("/api/dashboard/trends"),
        api.get("/api/dashboard/lsr"),
        api.get("/api/dashboard/barriers"),
        api.get("/api/dashboard/sites"),
        api.get("/api/dashboard/heatmap"),
        api.get("/api/dashboard/lsr-by-site"),
        api.get("/api/metrics/response-time").catch(() => ({ data: null })),
      ]);
      setSummary(s.data);
      setTrends(t.data);
      setLsr(l.data);
      setBarriers(b.data);
      setSites(sitesResp.data.ranking.slice(0, 5));
      setHeatmap(heatmapResp.data.matrix);
      setLsrBySite(lsrSiteResp.data);
      setResponseTime(rt.data);
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to load dashboard data."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (loading) return <LoadingState label="Loading HSE dashboard..." />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  const sifPieData = [
    { name: "HIGH", value: summary.sif_high },
    { name: "MEDIUM", value: summary.sif_medium },
    { name: "LOW", value: summary.sif_low },
    { name: "NON_SIF", value: summary.non_sif },
    { name: "REVIEW", value: summary.review_queue_classified_review },
  ].filter((d) => d.value > 0);

  const lsrSiteColors = ["#e29a26", "#17a396", "#293563", "#e0264f", "#7c5cf0", "#189a6b", "#f2932c", "#d4a017", "#3a477a"];

  return (
    <div>
      <PageHeader
        eyebrow="Live intelligence"
        title="HSE Precursor Intelligence Dashboard"
        description="SIF-precursor reports, IOGP Life-Saving Rule distribution, barrier failures and site/activity risk ranking — all computed from the current dataset."
        actions={<SyntheticBadge />}
      />

      <div className="mb-6 grid grid-cols-2 gap-3.5 sm:grid-cols-3 lg:grid-cols-7">
        <KpiCard label="Total Reports" value={summary.total_reports} icon={<IconList className="h-4 w-4" />} />
        <KpiCard label="SIF-Potential" value={summary.sif_high + summary.sif_medium} accent="medium" icon={<IconFlame className="h-4 w-4" />} />
        <KpiCard label="High Risk" value={summary.sif_high} accent="high" icon={<IconAlertTriangle className="h-4 w-4" />} />
        <KpiCard
          label="AI Abstained"
          value={summary.review_queue_classified_review}
          accent="review"
          icon={<IconEval className="h-4 w-4" />}
          sub={`${summary.review_queue_total} total flagged for review`}
        />
        <KpiCard label="Repeat Precursors" value={summary.repeat_precursor_reports} accent="medium" icon={<IconTrend className="h-4 w-4" />} />
        <KpiCard label="Critical Barrier Failures" value={summary.critical_barrier_failures} accent="high" icon={<IconBolt className="h-4 w-4" />} />
        <KpiCard
          label="Median ack time"
          value={
            responseTime?.overall?.median_seconds != null
              ? `${Math.round(responseTime.overall.median_seconds)}s`
              : "—"
          }
          accent="medium"
          icon={<IconCheckShield className="h-4 w-4" />}
          sub={
            responseTime?.overall?.count
              ? `${responseTime.overall.count} acknowledged alerts`
              : "No acknowledgments yet"
          }
        />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <ChartCard title="SIF Trend Over Time" icon={<IconTrend className="h-4 w-4" />} className="lg:col-span-2">
          {trends.sif_trend.length === 0 ? (
            <p className="py-10 text-center text-sm text-ink_text-muted">No trend data yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={trends.sif_trend}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} vertical={false} />
                <XAxis dataKey="month" tick={TICK} axisLine={{ stroke: CHART_GRID }} tickLine={false} />
                <YAxis tick={TICK} allowDecimals={false} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid #e3e6f0", fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line type="monotone" dataKey="high" stroke={SIF_COLORS.HIGH} name="HIGH" strokeWidth={2.25} dot={false} />
                <Line type="monotone" dataKey="medium" stroke={SIF_COLORS.MEDIUM} name="MEDIUM" strokeWidth={2.25} dot={false} />
                <Line type="monotone" dataKey="low" stroke={SIF_COLORS.LOW} name="LOW" strokeWidth={1.75} dot={false} />
                <Line type="monotone" dataKey="non_sif" stroke={SIF_COLORS.NON_SIF} name="NON-SIF" strokeWidth={1.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard title="SIF Classification Split" icon={<IconEval className="h-4 w-4" />}>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={sifPieData} dataKey="value" nameKey="name" innerRadius={48} outerRadius={88} paddingAngle={2}>
                {sifPieData.map((entry) => (
                  <Cell key={entry.name} fill={SIF_COLORS[entry.name]} stroke="none" />
                ))}
              </Pie>
              <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid #e3e6f0", fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="IOGP Life-Saving Rule Distribution" icon={<IconList className="h-4 w-4" />}>
          {lsr.length === 0 ? (
            <p className="py-10 text-center text-sm text-ink_text-muted">No SIF-positive reports yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={lsr} layout="vertical" margin={{ left: 40 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} horizontal={false} />
                <XAxis type="number" tick={TICK} allowDecimals={false} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="lsr" width={130} tick={{ fontSize: 10, fill: "#57607a" }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid #e3e6f0", fontSize: 12 }} />
                <Bar dataKey="count" fill="#e29a26" radius={[0, 6, 6, 0]} maxBarSize={16} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard title="Barrier Failures" subtitle="Non-effective status only" icon={<IconBolt className="h-4 w-4" />}>
          {barriers.length === 0 ? (
            <p className="py-10 text-center text-sm text-ink_text-muted">No barrier failures recorded.</p>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={barriers.slice(0, 6)} margin={{ bottom: 40 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} vertical={false} />
                <XAxis dataKey="barrier" tick={{ fontSize: 9, fill: "#8b93aa" }} angle={-25} textAnchor="end" interval={0} axisLine={false} tickLine={false} />
                <YAxis tick={TICK} allowDecimals={false} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid #e3e6f0", fontSize: 12 }} />
                <Bar dataKey="count" fill="#e0264f" radius={[6, 6, 0, 0]} maxBarSize={22} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard title="Top Sites by SIF-Precursor Density" icon={<IconRank className="h-4 w-4" />}>
          {sites.length === 0 ? (
            <p className="py-10 text-center text-sm text-ink_text-muted">No site data yet.</p>
          ) : (
            <div className="space-y-2.5">
              {sites.map((s) => (
                <div key={s.name}>
                  <div className="mb-1 flex items-center justify-between text-[12px]">
                    <span className="font-semibold text-ink_text-primary">{s.name}</span>
                    <span className="font-bold tabular-nums text-ink_text-secondary">{(s.density * 100).toFixed(0)}%</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-surface-muted">
                    <div
                      className="h-1.5 rounded-full bg-gradient-to-r from-accent-400 to-risk-high"
                      style={{ width: `${Math.min(100, s.density * 100)}%` }}
                    />
                  </div>
                  <p className="mt-0.5 text-[10.5px] text-ink_text-muted">{s.sif_positive_reports} / {s.total_reports} reports</p>
                </div>
              ))}
              <Link to="/rankings" className="inline-flex items-center gap-1 pt-1 text-[12px] font-bold text-accent-700 hover:underline">
                Full ranking <IconArrowUpRight className="h-3 w-3" />
              </Link>
            </div>
          )}
        </ChartCard>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-5 xl:grid-cols-5">
        <ChartCard
          title="Site x Activity Risk Heatmap"
          subtitle="SIF-precursor density by combination — report-volume normalized, not exposure-hours"
          icon={<IconRank className="h-4 w-4" />}
          className="xl:col-span-3"
        >
          <SiteActivityHeatmap matrix={heatmap} />
        </ChartCard>

        <ChartCard
          title="Cross-Site LSR Comparison"
          subtitle="SIF-positive (HIGH/MEDIUM) reports by Life-Saving Rule"
          icon={<IconTrend className="h-4 w-4" />}
          className="xl:col-span-2"
        >
          {!lsrBySite || lsrBySite.series.length === 0 ? (
            <p className="py-10 text-center text-sm text-ink_text-muted">Not enough site data yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={lsrBySite.series} layout="vertical" margin={{ left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} horizontal={false} />
                <XAxis type="number" tick={TICK} allowDecimals={false} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="site" width={92} tick={{ fontSize: 10, fill: "#57607a" }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid #e3e6f0", fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 9.5 }} />
                {lsrBySite.lsr_names.map((name, i) => (
                  <Bar key={name} dataKey={name} stackId="lsr" fill={lsrSiteColors[i % lsrSiteColors.length]} radius={i === lsrBySite.lsr_names.length - 1 ? [0, 4, 4, 0] : 0} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>
    </div>
  );
}
