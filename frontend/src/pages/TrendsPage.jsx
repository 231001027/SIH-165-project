import { useEffect, useState } from "react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, PieChart, Pie, Cell, Legend } from "recharts";
import api, { extractErrorMessage } from "../services/api";
import PageHeader from "../components/PageHeader";
import { LoadingState, ErrorState } from "../components/StateViews";
import { Card, CardHeader } from "../components/ui";
import { IconSparkle, IconFlame, IconBolt } from "../components/icons";

const COLORS = ["#e29a26", "#e0264f", "#f2932c", "#d4a017", "#189a6b", "#7c5cf0", "#17a396", "#293563"];
const CHART_GRID = "#eceef6";
const TICK = { fontSize: 11, fill: "#8b93aa" };

export default function TrendsPage() {
  const [trends, setTrends] = useState(null);
  const [hazards, setHazards] = useState(null);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      const [t, h] = await Promise.all([api.get("/api/dashboard/trends"), api.get("/api/dashboard/hazards")]);
      setTrends(t.data);
      setHazards(h.data);
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to load trends."));
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!trends || !hazards) return <LoadingState label="Loading trends..." />;

  return (
    <div>
      <PageHeader
        eyebrow="Pattern intelligence"
        title="Pattern & Trend Intelligence"
        description="Month-over-month precursor patterns, plus hazard and energy-source distribution across all analyzed reports."
      />

      <Card className="mb-5">
        <CardHeader title="What Changed?" subtitle="Observed period-over-period shifts" icon={<IconSparkle className="h-4 w-4" />} />
        {trends.what_changed.length === 0 ? (
          <p className="text-sm text-ink_text-muted">
            Not enough month-over-month data yet to compute a reliable "what changed" statement (minimum sample size not met).
          </p>
        ) : (
          <ul className="space-y-2">
            {trends.what_changed.map((w, i) => (
              <li key={i} className="rounded-xl bg-surface-muted p-3.5 text-[13px] leading-relaxed text-ink_text-primary">
                {w.statement}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title="Hazard Distribution" icon={<IconFlame className="h-4 w-4" />} />
          {hazards.hazards.length === 0 ? (
            <p className="py-10 text-center text-sm text-ink_text-muted">No hazard data yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie data={hazards.hazards} dataKey="count" nameKey="hazard" innerRadius={50} outerRadius={95} paddingAngle={2}>
                  {hazards.hazards.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} stroke="none" />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid #e3e6f0", fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card>
          <CardHeader title="Energy Source Distribution" icon={<IconBolt className="h-4 w-4" />} />
          {hazards.energy_sources.length === 0 ? (
            <p className="py-10 text-center text-sm text-ink_text-muted">No energy source data yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={hazards.energy_sources}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} vertical={false} />
                <XAxis dataKey="energy_category" tick={{ fontSize: 10, fill: "#57607a" }} axisLine={false} tickLine={false} />
                <YAxis tick={TICK} allowDecimals={false} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid #e3e6f0", fontSize: 12 }} />
                <Bar dataKey="count" fill="#e29a26" radius={[6, 6, 0, 0]} maxBarSize={36} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>
    </div>
  );
}
