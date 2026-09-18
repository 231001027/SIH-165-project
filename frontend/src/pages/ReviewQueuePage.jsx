import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { extractErrorMessage } from "../services/api";
import PageHeader from "../components/PageHeader";
import { SifBadge } from "../components/Badges";
import { LoadingState, ErrorState, EmptyState } from "../components/StateViews";
import { Card, Button, Select, Input, Label } from "../components/ui";
import { IconCheckShield } from "../components/icons";
import { useAuth } from "../context/AuthContext";

const SIF_OPTIONS = ["HIGH", "MEDIUM", "LOW", "NON_SIF", "REVIEW"];
const PROXIMITY_OPTIONS = ["HIGH", "MEDIUM", "LOW", "NONE"];

const FIELD_DEFS = [
  { key: "sif_classification", label: "SIF Potential", type: "select", options: SIF_OPTIONS },
  { key: "primary_lsr", label: "Life-Saving Rule", type: "text" },
  { key: "hazard", label: "Hazard", type: "text" },
  { key: "energy_source", label: "Energy Source", type: "text" },
  { key: "exposure_description", label: "Exposure", type: "text" },
  { key: "exposure_proximity", label: "Exposure Proximity", type: "select", options: PROXIMITY_OPTIONS },
  { key: "activity_extracted", label: "Activity", type: "text" },
  { key: "location_extracted", label: "Location", type: "text" },
  { key: "potential_consequence", label: "Potential Consequence", type: "text" },
];

function blankCorrections(item) {
  const out = {};
  for (const f of FIELD_DEFS) {
    out[f.key] = item[f.key] ?? "";
  }
  if (!out.sif_classification || out.sif_classification === "REVIEW") {
    out.sif_classification = "MEDIUM";
  }
  return out;
}

export default function ReviewQueuePage() {
  const { hasRole } = useAuth();
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");
  const [modifyTarget, setModifyTarget] = useState(null);
  const [corrections, setCorrections] = useState({});
  const [modifyReason, setModifyReason] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [retrainMsg, setRetrainMsg] = useState("");

  async function load() {
    setError("");
    try {
      const resp = await api.get("/api/review");
      setItems(resp.data);
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to load review queue."));
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function act(reportId, action, extra = {}) {
    setBusyId(reportId);
    try {
      await api.post(`/api/review/${reportId}`, { action, ...extra });
      await load();
      setModifyTarget(null);
    } catch (err) {
      setError(extractErrorMessage(err, "Review action failed."));
    } finally {
      setBusyId(null);
    }
  }

  async function runRetrain() {
    setRetrainMsg("");
    try {
      const resp = await api.post("/api/review/retrain");
      setRetrainMsg(
        resp.data.trained
          ? `Retrained on ${resp.data.n_train} rows (${resp.data.feedback_overrides} feedback overrides). Train accuracy: ${(resp.data.train_accuracy * 100).toFixed(1)}%.`
          : `Retrain skipped: ${resp.data.reason || "insufficient data"}`
      );
    } catch (err) {
      setRetrainMsg(extractErrorMessage(err, "Retrain failed."));
    }
  }

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!items) return <LoadingState label="Loading review queue..." />;

  return (
    <div>
      <PageHeader
        eyebrow="Human-in-the-loop"
        title="Human Review Queue"
        description="Reports where the AI abstained (REVIEW), routed weak-confidence evidence, or an analyst escalated. Approve, modify (all analysis fields), reject or escalate each case."
      />

                  {hasRole("ADMIN") && (
        <Card className="mb-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-[13px] text-ink_text-secondary">
              Retrain the SIF classifier from current labels plus stored Feedback corrections (PUBLIC_CORPUS excluded).
            </p>
            <Button variant="primary" size="sm" onClick={runRetrain}>Retrain from feedback</Button>
          </div>
          {retrainMsg && <p className="mt-2 text-[12px] text-ink_text-muted">{retrainMsg}</p>}
        </Card>
      )}

      {items.length === 0 ? (
        <EmptyState
          icon={<IconCheckShield className="h-5 w-5" />}
          title="Review queue is empty"
          description="Nothing currently needs human attention. New REVIEW-classified or low-confidence reports will appear here automatically."
        />
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <Card key={item.report_id}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link to={`/reports/${item.report_id}`} className="font-mono text-[13px] font-extrabold text-accent-700 hover:underline">
                      {item.report_code}
                    </Link>
                    <SifBadge value={item.sif_classification} />
                    <span className="text-[11px] font-semibold text-ink_text-muted">{item.confidence}% confidence</span>
                  </div>
                  <p className="mt-1.5 line-clamp-2 text-[13px] text-ink_text-secondary">{item.narrative}</p>
                  {item.abstain_reason && (
                    item.sif_classification === "UNSUPPORTED_LANGUAGE" ? (
                      <p className="mt-1 rounded-lg border border-amber-300 bg-amber-50 px-2.5 py-1.5 text-[11.5px] font-medium text-amber-950">
                        {item.abstain_reason}
                      </p>
                    ) : (
                      <p className="mt-1 text-[11.5px] italic text-risk-review">{item.abstain_reason}</p>
                    )
                  )}
                  <p className="mt-1 text-[11px] text-ink_text-muted">
                    {item.site || "Unknown site"} · {item.activity || "Unknown activity"} · {item.primary_lsr || "No applicable rule"}
                  </p>
                </div>
                <div className="flex flex-shrink-0 gap-2">
                  <Button variant="success" size="sm" disabled={busyId === item.report_id} onClick={() => act(item.report_id, "APPROVE")}>Approve</Button>
                  <Button
                    variant="primary"
                    size="sm"
                    disabled={busyId === item.report_id}
                    onClick={() => {
                      setModifyTarget(item.report_id);
                      setCorrections(blankCorrections(item));
                      setModifyReason("");
                    }}
                  >
                    Modify
                  </Button>
                  <Button variant="outline" size="sm" disabled={busyId === item.report_id} onClick={() => act(item.report_id, "REJECT")}>Reject</Button>
                  <Button
                    variant="danger"
                    size="sm"
                    disabled={busyId === item.report_id}
                    onClick={() => act(item.report_id, "ESCALATE", { reason: "Escalated for senior HSE attention." })}
                  >
                    Escalate
                  </Button>
                </div>
              </div>

              {modifyTarget === item.report_id && (
                <div className="mt-3.5 rounded-xl border border-accent-200 bg-accent-50/60 p-3.5">
                  <div className="grid gap-3 sm:grid-cols-2">
                    {FIELD_DEFS.map((f) => (
                      <div key={f.key}>
                        <Label>{f.label}</Label>
                        {f.type === "select" ? (
                          <Select
                            value={corrections[f.key] || ""}
                            onChange={(e) => setCorrections((c) => ({ ...c, [f.key]: e.target.value }))}
                          >
                            {f.options.map((opt) => (
                              <option key={opt} value={opt}>{opt}</option>
                            ))}
                          </Select>
                        ) : (
                          <Input
                            type="text"
                            value={corrections[f.key] || ""}
                            onChange={(e) => setCorrections((c) => ({ ...c, [f.key]: e.target.value }))}
                          />
                        )}
                      </div>
                    ))}
                  </div>
                  <div className="mt-3 flex flex-wrap items-end gap-3">
                    <div className="min-w-[220px] flex-1">
                      <Label>Reason (required for audit trail)</Label>
                      <Input
                        type="text"
                        value={modifyReason}
                        onChange={(e) => setModifyReason(e.target.value)}
                        placeholder="Why are these fields being corrected?"
                      />
                    </div>
                    <Button
                      variant="primary"
                      size="md"
                      disabled={!modifyReason.trim() || busyId === item.report_id}
                      onClick={() =>
                        act(item.report_id, "MODIFY", {
                          reason: modifyReason,
                          corrected_fields: corrections,
                        })
                      }
                    >
                      Save Correction
                    </Button>
                    <Button variant="ghost" size="md" onClick={() => setModifyTarget(null)}>Cancel</Button>
                  </div>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
