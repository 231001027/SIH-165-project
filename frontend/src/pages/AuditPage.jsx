import { useEffect, useState } from "react";
import api, { extractErrorMessage } from "../services/api";
import PageHeader from "../components/PageHeader";
import { LoadingState, ErrorState, EmptyState } from "../components/StateViews";
import { Card } from "../components/ui";
import { IconLock } from "../components/icons";

export default function AuditPage() {
  const [logs, setLogs] = useState(null);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      const resp = await api.get("/api/audit");
      setLogs(resp.data);
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to load audit trail."));
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!logs) return <LoadingState label="Loading audit trail..." />;

  return (
    <div>
      <PageHeader
        eyebrow="Admin"
        title="Audit Trail"
        description="Append-only log of every automated and human action. Full report narratives are never logged here — only structured metadata (admin-only view)."
      />
      {logs.length === 0 ? (
        <EmptyState icon={<IconLock className="h-5 w-5" />} title="No audit events yet" />
      ) : (
        <Card padded={false} className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-line bg-surface-muted text-left text-[10.5px] font-bold uppercase tracking-wide text-ink_text-muted">
                <tr>
                  <th className="px-3.5 py-2.5">Time</th>
                  <th className="px-3.5 py-2.5">Action</th>
                  <th className="px-3.5 py-2.5">Entity</th>
                  <th className="px-3.5 py-2.5">Actor</th>
                  <th className="px-3.5 py-2.5">Detail</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((l) => (
                  <tr key={l.id} className="border-t border-line/70">
                    <td className="whitespace-nowrap px-3.5 py-2 text-ink_text-muted">{new Date(l.created_at).toLocaleString()}</td>
                    <td className="px-3.5 py-2 font-bold text-ink_text-primary">{l.action}</td>
                    <td className="px-3.5 py-2 text-ink_text-secondary">{l.entity_type} #{l.entity_id}</td>
                    <td className="px-3.5 py-2 text-ink_text-secondary">{l.actor}</td>
                    <td className="px-3.5 py-2 font-mono text-[11px] text-ink_text-muted">{JSON.stringify(l.payload)}</td>
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
