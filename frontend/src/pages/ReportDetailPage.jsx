import { useEffect, useState, useCallback } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import api, { extractErrorMessage } from "../services/api";
import { LoadingState, ErrorState } from "../components/StateViews";
import { SifBadge, ReasonCodeChip, ReportTypeBadge, SyntheticBadge, ReferenceIncidentBadge } from "../components/Badges";
import { Card, CardHeader, Button, Textarea, Field } from "../components/ui";
import BarrierChainDiagram from "../components/BarrierChainDiagram";
import { useAuth } from "../context/AuthContext";
import {
  IconArrowLeft, IconCheckShield, IconBolt, IconLayers, IconSparkle, IconLink, IconEval, IconAlertTriangle,
} from "../components/icons";

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

  const load = useCallback(async () => {
    setError("");
    try {
      const [r, s] = await Promise.all([
        api.get(`/api/reports/${id}`),
        api.get(`/api/reports/${id}/similar`),
      ]);
      setReport(r.data);
      setSimilar(s.data);
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

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!report) return <LoadingState label="Loading report..." />;

  const a = report.analysis;

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
              {report.narrative}
            </p>
            <div className="mt-3.5 grid grid-cols-3 gap-3">
              <Field label="Site" value={report.site} />
              <Field label="Activity" value={report.activity} />
              <Field label="Location" value={report.location} />
            </div>
          </Section>

          {a ? (
            <>
              <Section
                title="AI SIF Assessment"
                icon={<IconAlertTriangle className="h-4 w-4" />}
                right={
                  <div className="flex items-center gap-2">
                    <SifBadge value={a.sif_classification} size="lg" pulse={a.sif_classification === "HIGH"} />
                    <span className="text-[13px] font-semibold text-ink_text-secondary">{a.confidence}% confidence</span>
                  </div>
                }
              >
                {a.review_required && (
                  <div className="mb-3.5 rounded-lg border border-risk-review/25 bg-risk-review/5 px-3.5 py-2.5 text-[13px] text-risk-review">
                    <p className="font-bold">Flagged for human HSE review.</p>
                    {a.abstain_reason && <p className="mt-0.5 text-[12px] text-risk-review/80">{a.abstain_reason}</p>}
                  </div>
                )}
                <div className="grid grid-cols-2 gap-3.5 sm:grid-cols-3">
                  <Field label="Risk Score (0-100, prototype)" value={a.risk_score} />
                  <Field label="Life-Saving Rule" value={a.primary_lsr} />
                  <Field label="LSR Confidence" value={a.primary_lsr_confidence != null ? `${a.primary_lsr_confidence}%` : "—"} />
                  <Field label="Secondary LSR" value={a.secondary_lsr} />
                  <Field label="Model Version" value={a.model_version} mono />
                  <Field label="Potential Consequence" value={a.potential_consequence} />
                </div>
              </Section>

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
                    .filter(([k, v]) => !["total", "_disclaimer", "standards_tags", "language_script", "language_abstention"].includes(k) && typeof v === "number")
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
                    <p className="text-[11px] font-semibold text-ink_text-secondary">Secondary standards tags (ISO 45001 / PSM-inspired overlays — not IOGP replacements)</p>
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
                {similar.map((s) =>
                  s.source === "PUBLIC_CORPUS" ? (
                    <a
                      key={s.report_id}
                      href={s.citation_url}
                      target="_blank"
                      rel="noreferrer"
                      className="block rounded-xl border border-accent-200 bg-accent-50/40 p-2.5 transition hover:border-accent-400"
                    >
                      <div className="flex items-center justify-between">
                        <ReferenceIncidentBadge />
                        <span className="text-[11px] font-bold text-ink_text-muted">{(s.similarity * 100).toFixed(0)}% similar</span>
                      </div>
                      <p className="mt-1.5 text-[12.5px] font-bold text-ink_text-primary">{s.citation_label}</p>
                      <p className="mt-0.5 text-[11px] text-ink_text-secondary">{s.life_saving_rule}</p>
                      {s.excerpt && (
                        <p className="mt-1.5 text-[11px] italic leading-snug text-ink_text-secondary">
                          “{s.excerpt}”
                        </p>
                      )}
                    </a>
                  ) : (
                    <Link
                      key={s.report_id}
                      to={`/reports/${s.report_id}`}
                      className="block rounded-xl border border-line p-2.5 transition hover:border-accent-300 hover:bg-accent-50/30"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-[12.5px] font-bold text-ink_text-primary">{s.report_code}</span>
                        <span className="text-[11px] font-bold text-ink_text-muted">{(s.similarity * 100).toFixed(0)}% similar</span>
                      </div>
                      <div className="mt-1.5 flex items-center gap-1.5">
                        {s.sif_potential && <SifBadge value={s.sif_potential} />}
                        <span className="text-[11px] text-ink_text-secondary">{s.life_saving_rule}</span>
                      </div>
                      <p className="mt-0.5 text-[11px] text-ink_text-muted">{s.site} · {s.activity}</p>
                      {s.excerpt && (
                        <p className="mt-1.5 text-[11px] italic leading-snug text-ink_text-secondary">
                          “{s.excerpt}”
                        </p>
                      )}
                    </Link>
                  )
                )}
              </div>
            )}
          </Section>

          {hasRole("ADMIN", "HSE_ANALYST") && (
            <Section title="Human Review" icon={<IconCheckShield className="h-4 w-4" />}>
              <Textarea
                rows={2}
                value={reviewReason}
                onChange={(e) => setReviewReason(e.target.value)}
                placeholder="Optional reason / notes..."
                className="mb-3"
              />
              <div className="grid grid-cols-2 gap-2">
                <Button variant="success" size="sm" disabled={reviewSubmitting} onClick={() => handleReview("APPROVE")}>Approve</Button>
                <Button variant="outline" size="sm" disabled={reviewSubmitting} onClick={() => handleReview("REJECT")}>Reject</Button>
                <Button variant="danger" size="sm" disabled={reviewSubmitting} onClick={() => handleReview("ESCALATE")}>Escalate</Button>
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
