import { useEffect, useState, useCallback } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import api, { extractErrorMessage } from "../services/api";
import { LoadingState, ErrorState } from "../components/StateViews";
import { SifBadge, ReasonCodeChip, ReportTypeBadge, SyntheticBadge, ReferenceIncidentBadge, UnsupportedLanguageBanner } from "../components/Badges";
import { Card, CardHeader, Button, Textarea, Field } from "../components/ui";
import BarrierChainDiagram from "../components/BarrierChainDiagram";
import PrecursorComparisonView from "../components/PrecursorComparisonView";
import { useAuth } from "../context/AuthContext";
import {
  IconArrowLeft, IconCheckShield, IconBolt, IconLayers, IconSparkle, IconLink, IconEval, IconAlertTriangle,
} from "../components/icons";

function highlightNarrative(text, spans) {
  if (!text) return null;
  const needles = (spans || []).filter(Boolean).sort((a, b) => b.length - a.length);
  if (!needles.length) return text;
  const lower = text.toLowerCase();
  const marks = [];
  for (const span of needles) {
    const idx = lower.indexOf(String(span).toLowerCase());
    if (idx >= 0) marks.push([idx, idx + span.length]);
  }
  if (!marks.length) return text;
  marks.sort((a, b) => a[0] - b[0]);
  const merged = [];
  for (const [s, e] of marks) {
    if (!merged.length || s > merged[merged.length - 1][1]) merged.push([s, e]);
    else merged[merged.length - 1][1] = Math.max(merged[merged.length - 1][1], e);
  }
  const parts = [];
  let cursor = 0;
  merged.forEach(([s, e], i) => {
    if (cursor < s) parts.push(text.slice(cursor, s));
    parts.push(
      <mark key={i} className="rounded bg-amber-200/80 px-0.5">{text.slice(s, e)}</mark>
    );
    cursor = e;
  });
  if (cursor < text.length) parts.push(text.slice(cursor));
  return parts;
}

function Section({ title, children, right, icon }) {
  return (
    <Card>
      <CardHeader title={title} right={right} icon={icon} />
      {children}
    </Card>
  );
}

export default function ReportDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { hasRole } = useAuth();

  const [report, setReport] = useState(null);
  const [similar, setSimilar] = useState(null);
  const [error, setError] = useState("");
  const [reanalyzing, setReanalyzing] = useState(false);
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  const [reviewReason, setReviewReason] = useState("");
  const [reviewMessage, setReviewMessage] = useState("");
  const [comparison, setComparison] = useState(null);
  const [compareBusy, setCompareBusy] = useState(false);
  const [notifications, setNotifications] = useState([]);

  const load = useCallback(async () => {
    setError("");
    try {
      const [r, s] = await Promise.all([
        api.get(`/api/reports/${id}`),
        api.get(`/api/reports/${id}/similar`),
      ]);
      setReport(r.data);
      setSimilar(s.data);
      try {
        const n = await api.get(`/api/reports/${id}/notifications`);
        setNotifications(n.data || []);
      } catch {
        setNotifications([]);
      }
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to load report."));
    }
  }, [id]);

  useEffect(() => {
    setReport(null);
    load();
  }, [load]);

  async function handleReanalyze() {
    setReanalyzing(true);
    try {
      await api.post(`/api/reports/${id}/analyze`);
      await load();
    } catch (err) {
      setError(extractErrorMessage(err, "Re-analysis failed."));
    } finally {
      setReanalyzing(false);
    }
  }

  async function handleReview(action) {
    setReviewSubmitting(true);
    setReviewMessage("");
    try {
      await api.post(`/api/review/${id}`, { action, reason: reviewReason || null });
      setReviewMessage(`Review recorded: ${action}.`);
      setReviewReason("");
      await load();
    } catch (err) {
      setReviewMessage(extractErrorMessage(err, "Failed to submit review."));
    } finally {
      setReviewSubmitting(false);
    }
  }

  async function openComparison(matchId) {
    setCompareBusy(true);
    setError("");
    try {
      const resp = await api.get(`/api/reports/${id}/compare/${matchId}`);
      setComparison(resp.data);
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to load precursor comparison."));
    } finally {
      setCompareBusy(false);
    }
  }

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!report) return <LoadingState label="Loading report..." />;

  const a = report.analysis;
  const narrativeSpans = [
    ...(a?.lsr_evidence || []).map((e) => (typeof e === "string" ? e : e?.text || e?.span || "")).filter(Boolean),
    ...(a?.barriers || []).map((b) => b.evidence_text).filter(Boolean),
  ];

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-2">
        <div>
          <button onClick={() => navigate(-1)} className="mb-1.5 inline-flex items-center gap-1 text-xs font-semibold text-accent-700 hover:underline">
            <IconArrowLeft className="h-3.5 w-3.5" /> Back
          </button>
          <h1 className="font-mono text-[20px] font-extrabold tracking-tight text-ink_text-primary">
            {report.report_code}
            <span className="ml-2 font-sans font-normal text-ink_text-muted">— {report.title || "Untitled report"}</span>
          </h1>
          <div className="mt-1.5 flex items-center gap-2">
            <ReportTypeBadge value={report.report_type} />
            {report.source === "SYNTHETIC_SEED" && <SyntheticBadge />}
            <span className="text-xs text-ink_text-muted">{new Date(report.occurred_at).toLocaleString()}</span>
          </div>
        </div>
        {hasRole("ADMIN", "HSE_ANALYST") && (
          <Button variant="outline" size="sm" onClick={handleReanalyze} disabled={reanalyzing} icon={<IconSparkle className="h-3.5 w-3.5" />}>
            {reanalyzing ? "Re-analyzing..." : "Re-run AI Analysis"}
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          <Section title="Original Narrative" icon={<IconLayers className="h-4 w-4" />}>
            <p className="whitespace-pre-wrap rounded-xl bg-surface-muted p-3.5 text-[13.5px] leading-relaxed text-ink_text-primary">
              {highlightNarrative(report.narrative, narrativeSpans)}
            </p>
            <div className="mt-3.5 grid grid-cols-3 gap-3">
              <Field label="Site" value={report.site} />
              <Field label="Activity" value={report.activity} />
              <Field label="Location" value={report.location} />
            </div>
          </Section>

          {a ? (
            <>
              {a.sif_classification === "UNSUPPORTED_LANGUAGE" && (
                <UnsupportedLanguageBanner message={a.abstain_reason} />
              )}

              <Section
                title={a.sif_classification === "UNSUPPORTED_LANGUAGE" ? "Analysis status" : "AI SIF Assessment"}
                icon={<IconAlertTriangle className="h-4 w-4" />}
                right={
                  <div className="flex items-center gap-2">
                    <SifBadge value={a.sif_classification} size="lg" pulse={a.sif_classification === "HIGH"} />
                    {a.sif_classification !== "UNSUPPORTED_LANGUAGE" && (
                      <span className="text-[13px] font-semibold text-ink_text-secondary">{a.confidence}% confidence</span>
                    )}
                  </div>
                }
              >
                {a.review_required && a.sif_classification !== "UNSUPPORTED_LANGUAGE" && (
                  <div className="mb-3.5 rounded-lg border border-risk-review/25 bg-risk-review/5 px-3.5 py-2.5 text-[13px] text-risk-review">
                    <p className="font-bold">Flagged for human HSE review.</p>
                    {a.abstain_reason && <p className="mt-0.5 text-[12px] text-risk-review/80">{a.abstain_reason}</p>}
                  </div>
                )}
                {a.sif_classification !== "UNSUPPORTED_LANGUAGE" && (
                <div className="grid grid-cols-2 gap-3.5 sm:grid-cols-3">
                  <Field label="Risk Score (0-100, prototype)" value={a.risk_score} />
                  <Field label="Life-Saving Rule" value={a.primary_lsr} />
                  <Field label="LSR Confidence" value={a.primary_lsr_confidence != null ? `${a.primary_lsr_confidence}%` : "—"} />
                  <Field label="Secondary LSR" value={a.secondary_lsr} />
                  <Field label="Model Version" value={a.model_version} mono />
                  <Field label="Potential Consequence" value={a.potential_consequence} />
                </div>
                )}
              </Section>

              {a.oisd_classification && a.sif_classification !== "UNSUPPORTED_LANGUAGE" && (
                <Section title="OISD / Hi-Po lens (separate from SIF band)" icon={<IconBolt className="h-4 w-4" />}>
                  <p className="mb-3 text-[11.5px] text-ink_text-muted">
                    OISD-style consequence–probability matrix (Kind-3 prototype). Does not replace the AI SIF assessment above.
                  </p>
                  <div className="grid grid-cols-2 gap-3.5 sm:grid-cols-3">
                    <Field label="Consequence" value={`${a.oisd_classification.consequence} — ${a.oisd_classification.consequence_level}`} />
                    <Field label="Probability" value={`${a.oisd_classification.probability} — ${a.oisd_classification.probability_level}`} />
                    <Field label="OISD band" value={a.oisd_classification.band} />
                    <Field label="Hi-Po Near Miss" value={a.oisd_classification.is_hipo ? "YES" : "No"} />
                  </div>
                  <p className="mt-3 rounded-lg border border-line bg-surface-muted/50 px-3 py-2 text-[12.5px] text-ink_text-secondary">
                    {a.oisd_classification.rationale}
                  </p>
                </Section>
              )}

              {notifications.length > 0 && (
                <Section title="Hi-Po / HIGH notifications" icon={<IconCheckShield className="h-4 w-4" />}>
                  <ul className="space-y-2 text-[12.5px]">
                    {notifications.map((n) => (
                      <li key={n.id} className="rounded-lg border border-line px-3 py-2">
                        <p className="font-semibold text-ink_text-primary">
                          Notified: {n.assignee_name || "Assignee"} ({n.band_at_trigger})
                        </p>
                        <p className="text-ink_text-muted">
                          Sent {n.sent_at ? new Date(n.sent_at).toLocaleString() : "—"}
                          {n.acknowledged_at
                            ? ` · Acknowledged ${new Date(n.acknowledged_at).toLocaleString()} (${n.acknowledged_action})`
                            : " · Pending acknowledgment"}
                        </p>
                      </li>
                    ))}
                  </ul>
                </Section>
              )}

              {a.original_prediction?.sif_classification &&
                  a.original_prediction.sif_classification !== a.sif_classification && (
                  <div className="rounded-lg border border-line bg-surface-muted/50 px-3.5 py-2.5 text-[12.5px] text-ink_text-secondary">
                    <p className="font-bold text-ink_text-primary">Original model prediction (pre-review)</p>
                    <p className="mt-0.5">
                      Snapshot: <span className="font-semibold">{a.original_prediction.sif_classification}</span>
                      {a.original_prediction.confidence != null && (
                        <> at {a.original_prediction.confidence}% confidence</>
                      )}
                      {" → "}current: <span className="font-semibold">{a.sif_classification}</span>
                    </p>
                  </div>
                )}
              {a.original_prediction?.sif_classification &&
                  a.original_prediction.sif_classification === a.sif_classification && (
                  <p className="text-[11px] text-ink_text-muted">
                    Original prediction snapshot: {a.original_prediction.sif_classification}
                    {a.original_prediction.confidence != null ? ` (${a.original_prediction.confidence}%)` : ""} — unchanged by review.
                  </p>
                )}
              {a.sif_classification === "UNSUPPORTED_LANGUAGE" && (
                  <p className="text-[13px] text-ink_text-secondary">
                    Routed to the human review queue. Re-submit an English narrative, or correct fields manually after review.
                  </p>
                )}

              {a.sif_classification !== "UNSUPPORTED_LANGUAGE" && (
              <>
              <Section title="Precursor Chain" icon={<IconBolt className="h-4 w-4" />} right={<span className="text-[11px] font-medium text-ink_text-muted">Hazard → Energy → Exposure → Barrier → Consequence</span>}>
                <BarrierChainDiagram
                  hazard={a.hazard}
                  energySource={a.energy_source}
                  exposureProximity={a.exposure_proximity}
                  exposureDescription={a.exposure_description}
                  barriers={a.barriers}
                  potentialConsequence={a.potential_consequence}
                />
              </Section>

              <Section title="Why Flagged?" icon={<IconSparkle className="h-4 w-4" />}>
                <p className="text-[13.5px] leading-relaxed text-ink_text-primary">{a.explanation_text}</p>
                <p className="mt-2.5 text-[11px] font-medium text-ink_text-muted">
                  Explanation source:{" "}
                  {a.explanation_source === "llm_enhanced" ? "LLM-enhanced (validated against extracted evidence)" : "Rule/embedding template (LLM not used or unavailable)"}
                </p>
                {a.reason_codes?.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {a.reason_codes.map((code) => (
                      <ReasonCodeChip key={code} code={code} />
                    ))}
                  </div>
                )}
              </Section>

              <Section title="Risk Score Breakdown" icon={<IconEval className="h-4 w-4" />}>
                <div className="space-y-2">
                  {Object.entries(a.risk_breakdown)
                    .filter(([k, v]) => !["total", "_disclaimer", "standards_tags", "language_script", "language_abstention", "analysis_status"].includes(k) && typeof v === "number")
                    .map(([k, v]) => (
                      <div key={k} className="flex items-center gap-2.5">
                        <span className="w-36 flex-shrink-0 text-[11.5px] font-semibold text-ink_text-secondary">{k.replace(/_/g, " ")}</span>
                        <div className="h-2 flex-1 rounded-full bg-surface-muted">
                          <div className="h-2 rounded-full bg-gradient-to-r from-accent-400 to-accent-600" style={{ width: `${Math.min(100, (v / 30) * 100)}%` }} />
                        </div>
                        <span className="w-9 flex-shrink-0 text-right text-[12px] font-bold tabular-nums text-ink_text-primary">{v}</span>
                      </div>
                    ))}
                </div>
                {Array.isArray(a.risk_breakdown?.standards_tags) && a.risk_breakdown.standards_tags.length > 0 && (
                  <div className="mt-3">
                    <p className="text-[11px] font-semibold text-ink_text-secondary">Secondary Kind-3 standards overlays (team-designed ISO/PSM-inspired tags — not Kind-1 derivations; see precursor_taxonomy.json)</p>
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {a.risk_breakdown.standards_tags.map((tag) => (
                        <span key={tag} className="rounded-md border border-line bg-surface-muted px-2 py-0.5 text-[10.5px] text-ink_text-secondary">{tag}</span>
                      ))}
                    </div>
                  </div>
                )}
                <p className="mt-3.5 text-[11px] italic text-ink_text-muted">{a.risk_breakdown._disclaimer}</p>
              </Section>
              </>
              )}
            </>
          ) : (
            <Section title="AI Analysis">
              <p className="text-sm text-ink_text-muted">This report has not been analyzed yet.</p>
            </Section>
          )}
        </div>

        <div className="space-y-5">
          <Section title="Similar Precursor Reports" icon={<IconLink className="h-4 w-4" />}>
            {!similar || similar.length === 0 ? (
              <p className="text-sm text-ink_text-muted">No similar reports found yet.</p>
            ) : (
              <div className="space-y-2">
                {similar.map((s) => (
                  <button
                    type="button"
                    key={s.report_id}
                    onClick={() => openComparison(s.report_id)}
                    disabled={compareBusy}
                    className="block w-full rounded-xl border border-line p-2.5 text-left transition hover:border-accent-300 hover:bg-accent-50/30 disabled:opacity-60"
                  >
                    <div className="flex items-center justify-between">
                      {s.source === "PUBLIC_CORPUS" ? <ReferenceIncidentBadge /> : (
                        <span className="font-mono text-[12.5px] font-bold text-ink_text-primary">{s.report_code}</span>
                      )}
                      <span className="text-[11px] font-bold text-ink_text-muted">{(s.similarity * 100).toFixed(0)}% similar</span>
                    </div>
                    <p className="mt-1.5 text-[12.5px] font-bold text-ink_text-primary">
                      {s.source === "PUBLIC_CORPUS" ? s.citation_label : s.title}
                    </p>
                    {s.source === "PUBLIC_CORPUS" && String(s.citation_label || "").includes("LIMITATION") && (
                      <p className="mt-1 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-[10.5px] font-medium leading-snug text-amber-900">
                        Source limitation: team-authored demo narrative grounded on the cited portal — not a verbatim annual-report case extract.
                      </p>
                    )}
                    <p className="mt-0.5 text-[11px] text-ink_text-secondary">{s.life_saving_rule}</p>
                    {s.excerpt && (
                      <p className="mt-1.5 text-[11px] italic leading-snug text-ink_text-secondary">“{s.excerpt}”</p>
                    )}
                    <p className="mt-1 text-[10.5px] font-semibold text-accent-700">Open cited comparison →</p>
                  </button>
                ))}
              </div>
            )}
            {comparison && (
              <PrecursorComparisonView comparison={comparison} onClose={() => setComparison(null)} />
            )}
          </Section>

          {hasRole("ADMIN", "HSE_ANALYST") && (
            <Section title="Human Review" icon={<IconCheckShield className="h-4 w-4" />}>
              <p className="mb-2 text-[11px] leading-snug text-ink_text-muted">
                Use <strong>Modify in Queue</strong> if the AI was wrong.
                Use <strong>Reject</strong> only if this item shouldn&apos;t be in the queue.
                <strong> Escalate</strong> requires a written reason below.
              </p>
              <Textarea
                rows={2}
                value={reviewReason}
                onChange={(e) => setReviewReason(e.target.value)}
                placeholder="Reason / notes (required for Escalate)..."
                className="mb-3"
              />
              <div className="grid grid-cols-2 gap-2">
                <Button variant="success" size="sm" disabled={reviewSubmitting} onClick={() => handleReview("APPROVE")}>Approve</Button>
                <Button variant="outline" size="sm" disabled={reviewSubmitting} onClick={() => handleReview("REJECT")}>Reject</Button>
                <Button
                  variant="danger"
                  size="sm"
                  disabled={reviewSubmitting || !reviewReason.trim()}
                  onClick={() => handleReview("ESCALATE")}
                >
                  Escalate
                </Button>
                <Button as={Link} to="/review" variant="ghost" size="sm">Modify in Queue</Button>
              </div>
              {reviewMessage && <p className="mt-2.5 text-xs text-ink_text-muted">{reviewMessage}</p>}
            </Section>
          )}
        </div>
      </div>
    </div>
  );
}
