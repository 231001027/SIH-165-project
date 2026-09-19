import { useEffect, useState } from "react";
import api, { extractErrorMessage } from "../services/api";
import PageHeader from "../components/PageHeader";
import { Card, Button, Input, Select, Label } from "../components/ui";
import { LoadingState, ErrorState } from "../components/StateViews";

const ROLES = ["SITE_HSE_MANAGER", "SITE_HSE_OFFICER", "UNIT_HEAD"];

export default function RoutingPage() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(null);
  const [draft, setDraft] = useState({});
  const [busy, setBusy] = useState(false);

  async function load() {
    setError("");
    try {
      const resp = await api.get("/api/routing");
      setRows(resp.data);
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to load routing config."));
    }
  }

  useEffect(() => {
    load();
  }, []);

  function startEdit(row) {
    setEditing(row.id);
    setDraft({
      site: row.site,
      role: row.role,
      person_name: row.person_name,
      email: row.email,
      is_active: row.is_active,
    });
  }

  async function save(id) {
    setBusy(true);
    try {
      await api.put(`/api/routing/${id}`, draft);
      setEditing(null);
      await load();
    } catch (err) {
      setError(extractErrorMessage(err, "Save failed."));
    } finally {
      setBusy(false);
    }
  }

  if (error && !rows) return <ErrorState message={error} onRetry={load} />;
  if (!rows) return <LoadingState label="Loading assignee routing..." />;

  return (
    <div>
      <PageHeader
        eyebrow="Admin"
        title="Hi-Po assignee routing"
        description="Demo site→HSE contact mapping for HIGH / Hi-Po push alerts. Not real OIL contacts — editable demo config."
      />
      {error && <p className="mb-3 text-[13px] text-risk-high">{error}</p>}
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-[12.5px]">
            <thead>
              <tr className="border-b border-line text-[11px] uppercase text-ink_text-muted">
                <th className="py-2 pr-2">Site</th>
                <th className="py-2 pr-2">Role</th>
                <th className="py-2 pr-2">Name</th>
                <th className="py-2 pr-2">Email</th>
                <th className="py-2 pr-2">Active</th>
                <th className="py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-b border-line/70">
                  {editing === row.id ? (
                    <>
                      <td className="py-2 pr-2"><Input value={draft.site} onChange={(e) => setDraft((d) => ({ ...d, site: e.target.value }))} /></td>
                      <td className="py-2 pr-2">
                        <Select value={draft.role} onChange={(e) => setDraft((d) => ({ ...d, role: e.target.value }))}>
                          {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                        </Select>
                      </td>
                      <td className="py-2 pr-2"><Input value={draft.person_name} onChange={(e) => setDraft((d) => ({ ...d, person_name: e.target.value }))} /></td>
                      <td className="py-2 pr-2"><Input value={draft.email} onChange={(e) => setDraft((d) => ({ ...d, email: e.target.value }))} /></td>
                      <td className="py-2 pr-2">
                        <Label className="inline-flex items-center gap-1">
                          <input type="checkbox" checked={!!draft.is_active} onChange={(e) => setDraft((d) => ({ ...d, is_active: e.target.checked }))} />
                          Active
                        </Label>
                      </td>
                      <td className="py-2">
                        <Button size="sm" variant="primary" disabled={busy} onClick={() => save(row.id)}>Save</Button>
                        <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="py-2 pr-2 font-medium">{row.site}</td>
                      <td className="py-2 pr-2">{row.role}</td>
                      <td className="py-2 pr-2">{row.person_name}</td>
                      <td className="py-2 pr-2 font-mono text-[11px]">{row.email}</td>
                      <td className="py-2 pr-2">{row.is_active ? "Yes" : "No"}</td>
                      <td className="py-2"><Button size="sm" variant="outline" onClick={() => startEdit(row)}>Edit</Button></td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
