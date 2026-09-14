import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { extractErrorMessage } from "../services/api";
import PageHeader from "../components/PageHeader";
import { SifBadge } from "../components/Badges";
import { LoadingState, ErrorState, EmptyState } from "../components/StateViews";
import { Card, Button } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { IconCluster, IconSparkle } from "../components/icons";

export default function ClustersPage() {
  const { hasRole } = useAuth();
  const [clusters, setClusters] = useState(null);
  const [selected, setSelected] = useState(null);
  const [members, setMembers] = useState(null);
  const [error, setError] = useState("");
  const [recomputing, setRecomputing] = useState(false);

  async function load() {
    setError("");
    try {
      const resp = await api.get("/api/clusters");
      setClusters(resp.data);
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to load clusters."));
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function openCluster(id) {
    setSelected(id);
    setMembers(null);
    try {
      const resp = await api.get(`/api/clusters/${id}`);
      setMembers(resp.data.members);
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to load cluster members."));
    }
  }

  async function recompute() {
    setRecomputing(true);
    try {
      await api.post("/api/clusters/recompute");
      await load();
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to recompute clusters."));
    } finally {
      setRecomputing(false);
    }
  }

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!clusters) return <LoadingState label="Loading precursor clusters..." />;

  return (
    <div>
      <PageHeader
        eyebrow="Pattern intelligence"
        title="Precursor Clusters"
        description="Semantic clustering (KMeans over local TF-IDF/SVD embeddings) of HIGH/MEDIUM SIF-potential reports, auto-labelled from each cluster's most distinctive terms — surfaces recurring patterns, e.g. repeated isolation-verification failures."
        actions={
          hasRole("ADMIN", "HSE_ANALYST") && (
            <Button variant="accent" size="md" icon={<IconSparkle className="h-4 w-4" />} disabled={recomputing} onClick={recompute}>
              {recomputing ? "Recomputing..." : "Recompute Clusters"}
            </Button>
          )
        }
      />

      {clusters.length === 0 ? (
        <EmptyState
          icon={<IconCluster className="h-5 w-5" />}
          title="No clusters yet"
          description="Clusters are computed once at least a handful of HIGH/MEDIUM SIF-potential reports exist. Submit a few reports, or seed the demo dataset."
        />
      ) : (
        <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2">
          {clusters.map((c) => (
            <button
              key={c.id}
              onClick={() => openCluster(c.id)}
              className={`rounded-2xl border p-4 text-left shadow-card transition ${
                selected === c.id ? "border-accent-400 bg-accent-50/50 ring-2 ring-accent-100" : "border-line bg-surface-raised hover:border-accent-300"
              }`}
            >
              <div className="flex items-center justify-between">
                <p className="font-bold text-ink_text-primary">{c.label}</p>
                <span className="rounded-full bg-ink-900/[0.06] px-2.5 py-0.5 text-[11px] font-bold text-ink-900">
                  {c.member_count} reports
                </span>
              </div>
              <p className="mt-1 text-[11.5px] text-ink_text-muted">
                Dominant LSR: {c.dominant_lsr || "mixed"} · Dominant site: {c.dominant_site || "mixed"}
              </p>
              <div className="mt-2.5 flex flex-wrap gap-1">
                {c.top_terms?.map((t) => (
                  <span key={t} className="rounded-md bg-surface-muted px-1.5 py-0.5 text-[10.5px] font-medium text-ink_text-secondary">{t}</span>
                ))}
              </div>
            </button>
          ))}
        </div>
      )}

      {selected && (
        <div className="mt-6">
          <p className="mb-2.5 text-[13px] font-bold text-ink_text-primary">Cluster Members</p>
          {!members ? (
            <LoadingState label="Loading members..." />
          ) : (
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              {members.map((m) => (
                <Link key={m.report_id} to={`/reports/${m.report_id}`}>
                  <Card hover className="!p-3">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[12.5px] font-bold text-ink_text-primary">{m.report_code}</span>
                      <SifBadge value={m.sif_potential} />
                    </div>
                    <p className="mt-1 text-[11.5px] text-ink_text-muted">{m.life_saving_rule} · {m.site}</p>
                  </Card>
                </Link>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
