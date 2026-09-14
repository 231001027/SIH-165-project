import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { extractErrorMessage } from "../services/api";
import PageHeader from "../components/PageHeader";
import { SifBadge } from "../components/Badges";
import { LoadingState, ErrorState, EmptyState } from "../components/StateViews";
import { Card, Button, Input, Select, Label } from "../components/ui";
import { IconPlus, IconFilter, IconX, IconList } from "../components/icons";

const EMPTY_FILTERS = {
  sif: "", search: "", report_type: "", site: "", activity: "", lsr: "", barrier: "",
  occurred_from: "", occurred_to: "",
};

export default function ReportsListPage() {
  const [reports, setReports] = useState(null);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [catalog, setCatalog] = useState({ sites: [], activities: [], barrierTypes: [], lsrRules: [] });
  const [showFilters, setShowFilters] = useState(false);

  async function loadCatalog() {
    try {
      const [sitesResp, activitiesResp, barriersResp, kbResp] = await Promise.all([
        api.get("/api/catalog/sites"),
        api.get("/api/catalog/activities"),
        api.get("/api/catalog/barrier-types"),
        api.get("/api/catalog/lsr-knowledge-base"),
      ]);
      setCatalog({
        sites: sitesResp.data,
        activities: activitiesResp.data,
        barrierTypes: barriersResp.data,
        lsrRules: kbResp.data.map((r) => r.rule),
      });
    } catch {
      // Non-critical -- filters simply render with fewer options if this fails.
    }
  }

  async function load() {
    setError("");
    try {
      const params = {};
      Object.entries(filters).forEach(([k, v]) => {
        if (v) params[k] = v;
      });
      const resp = await api.get("/api/reports", { params });
      setReports(resp.data);
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to load reports."));
    }
  }

  useEffect(() => {
    loadCatalog();
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleFilterSubmit(e) {
    e.preventDefault();
    setReports(null);
    load();
  }

  function clearFilters() {
    setFilters(EMPTY_FILTERS);
    setReports(null);
    setTimeout(load, 0);
  }

  const activeFilterCount = Object.values(filters).filter(Boolean).length;

  return (
    <div>
      <PageHeader
        eyebrow="Reports"
        title="Safety Reports"
        description="All UA/UC, near-miss and incident reports with AI-assigned SIF potential, confidence and IOGP Life-Saving Rule."
        actions={
          <>
            <Button variant="outline" size="md" icon={<IconFilter className="h-4 w-4" />} onClick={() => setShowFilters((s) => !s)}>
              Filters {activeFilterCount > 0 && `(${activeFilterCount})`}
            </Button>
            <Button as={Link} to="/reports/new" variant="accent" size="md" icon={<IconPlus className="h-4 w-4" />}>
              New Report
            </Button>
          </>
        }
      />

      {showFilters && (
        <Card className="mb-4">
          <form onSubmit={handleFilterSubmit} className="grid grid-cols-2 gap-3.5 sm:grid-cols-3 lg:grid-cols-5">
            <div>
              <Label>SIF Potential</Label>
              <Select value={filters.sif} onChange={(e) => setFilters((f) => ({ ...f, sif: e.target.value }))} className="w-full">
                <option value="">All</option>
                {["HIGH", "MEDIUM", "LOW", "NON_SIF", "REVIEW"].map((v) => (
                  <option key={v} value={v}>{v === "NON_SIF" ? "NON-SIF" : v}</option>
                ))}
              </Select>
            </div>
            <div>
              <Label>Report Type</Label>
              <Select value={filters.report_type} onChange={(e) => setFilters((f) => ({ ...f, report_type: e.target.value }))} className="w-full">
                <option value="">All</option>
                <option value="UNSAFE_ACT">Unsafe Act</option>
                <option value="UNSAFE_CONDITION">Unsafe Condition</option>
                <option value="NEAR_MISS">Near Miss</option>
                <option value="INCIDENT">Incident</option>
              </Select>
            </div>
            <div>
              <Label>Site</Label>
              <Select value={filters.site} onChange={(e) => setFilters((f) => ({ ...f, site: e.target.value }))} className="w-full">
                <option value="">All sites</option>
                {catalog.sites.map((s) => <option key={s.id} value={s.name}>{s.name}</option>)}
              </Select>
            </div>
            <div>
              <Label>Activity</Label>
              <Select value={filters.activity} onChange={(e) => setFilters((f) => ({ ...f, activity: e.target.value }))} className="w-full">
                <option value="">All activities</option>
                {catalog.activities.map((a) => <option key={a.id} value={a.name}>{a.name}</option>)}
              </Select>
            </div>
            <div>
              <Label>Life-Saving Rule</Label>
              <Select value={filters.lsr} onChange={(e) => setFilters((f) => ({ ...f, lsr: e.target.value }))} className="w-full">
                <option value="">All rules</option>
                {catalog.lsrRules.map((r) => <option key={r} value={r}>{r}</option>)}
              </Select>
            </div>
            <div>
              <Label>Barrier</Label>
              <Select value={filters.barrier} onChange={(e) => setFilters((f) => ({ ...f, barrier: e.target.value }))} className="w-full">
                <option value="">All barriers</option>
                {catalog.barrierTypes.map((b) => <option key={b} value={b}>{b}</option>)}
              </Select>
            </div>
            <div>
              <Label>From date</Label>
              <Input type="date" value={filters.occurred_from} onChange={(e) => setFilters((f) => ({ ...f, occurred_from: e.target.value }))} />
            </div>
            <div>
              <Label>To date</Label>
              <Input type="date" value={filters.occurred_to} onChange={(e) => setFilters((f) => ({ ...f, occurred_to: e.target.value }))} />
            </div>
            <div className="sm:col-span-1 lg:col-span-2">
              <Label>Search narrative / title</Label>
              <Input
                type="text"
                value={filters.search}
                onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))}
                placeholder="e.g. isolation, flange, confined space..."
              />
            </div>
            <div className="col-span-2 flex items-end gap-2 sm:col-span-3 lg:col-span-5">
              <Button type="submit" variant="primary" size="md">Apply Filters</Button>
              <Button type="button" variant="ghost" size="md" icon={<IconX className="h-3.5 w-3.5" />} onClick={clearFilters}>
                Clear
              </Button>
            </div>
          </form>
        </Card>
      )}

      {error && <ErrorState message={error} onRetry={load} />}
      {!error && reports === null && <LoadingState label="Loading reports..." />}
      {!error && reports && reports.length === 0 && (
        <EmptyState
          icon={<IconList className="h-5 w-5" />}
          title="No reports match these filters"
          description="Try clearing filters or submit a new report."
        />
      )}
      {!error && reports && reports.length > 0 && (
        <Card padded={false} className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-line bg-surface-muted text-left text-[10.5px] font-bold uppercase tracking-wide text-ink_text-muted">
                <tr>
                  <th className="px-4 py-2.5">Report</th>
                  <th className="px-4 py-2.5">SIF</th>
                  <th className="px-4 py-2.5">Confidence</th>
                  <th className="px-4 py-2.5">LSR</th>
                  <th className="px-4 py-2.5">Site</th>
                  <th className="px-4 py-2.5">Activity</th>
                  <th className="px-4 py-2.5">Date</th>
                  <th className="px-4 py-2.5"></th>
                </tr>
              </thead>
              <tbody>
                {reports.map((r) => (
                  <tr key={r.id} className="border-t border-line/70 transition hover:bg-accent-50/30">
                    <td className="px-4 py-2.5">
                      <p className="font-mono text-[12.5px] font-bold text-ink_text-primary">{r.report_code}</p>
                      <p className="max-w-xs truncate text-[11.5px] text-ink_text-muted">{r.title || "Untitled"}</p>
                    </td>
                    <td className="px-4 py-2.5">{r.sif_classification ? <SifBadge value={r.sif_classification} /> : "-"}</td>
                    <td className="px-4 py-2.5 tabular-nums text-ink_text-secondary">{r.confidence != null ? `${r.confidence}%` : "-"}</td>
                    <td className="px-4 py-2.5 text-ink_text-secondary">{r.primary_lsr || "-"}</td>
                    <td className="px-4 py-2.5 text-ink_text-secondary">{r.site || "-"}</td>
                    <td className="px-4 py-2.5 text-ink_text-secondary">{r.activity || "-"}</td>
                    <td className="px-4 py-2.5 text-ink_text-muted">{new Date(r.occurred_at).toLocaleDateString()}</td>
                    <td className="px-4 py-2.5">
                      <Link to={`/reports/${r.id}`} className="font-bold text-accent-700 hover:underline">View</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
