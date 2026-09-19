import { useEffect, useState } from "react";
import api, { extractErrorMessage } from "../services/api";
import PageHeader from "../components/PageHeader";
import { LoadingState, ErrorState } from "../components/StateViews";
import { Card, CardHeader } from "../components/ui";
import { IconEval, IconList, IconCheckShield, IconInfo } from "../components/icons";

function MetricCard({ label, value, warn }) {
  return (
    <div className={`rounded-xl border p-4 text-center ${warn ? "border-risk-medium/30 bg-risk-medium/5" : "border-line bg-white"}`}>
      <p className={`text-2xl font-extrabold tabular-nums ${warn ? "text-risk-medium" : "text-ink_text-primary"}`}>{value}</p>
      <p className="mt-1 text-[11px] font-semibold text-ink_text-muted">{label}</p>
    </div>
  );
}

export default function EvaluationPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      const resp = await api.get("/api/evaluation");
      setData(resp.data);
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to load evaluation metrics."));
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data) return <LoadingState label="Computing evaluation metrics..." />;

  const sif = data.sif_classification;
  const lsr = data.lsr_mapping;
  const review = data.human_review;

  return (
    <div>
      <PageHeader eyebrow="Trust layer" title="Model Evaluation" description="Metrics computed against the held-out gold-set evaluation split." />

      <div className="mb-6 flex items-start gap-2.5 rounded-xl border border-accent-200 bg-accent-50 px-4 py-3 text-[13px] text-accent-800">
        <IconInfo className="mt-0.5 h-4 w-4 flex-shrink-0" />
        {data.disclaimer}
      </div>

      <div className="mb-5 grid grid-cols-1 gap-5 xl:grid-cols-2">
        <Card className="min-w-0">
          <CardHeader title="SIF Classification" icon={<IconEval className="h-4 w-4" />} />
          {sif.insufficient_data ? (
            <p className="text-sm text-ink_text-muted">{sif.message}</p>
          ) : (
            <>
              <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
                <MetricCard label="Test-set cases" value={sif.n_cases} />
                <MetricCard label="Macro F1" value={sif.macro_f1} />
                <MetricCard
                  label="False-Negative Rate (HIGH/MEDIUM)"
                  value={sif.false_negative_rate_high_medium ?? "n/a"}
                  warn={sif.false_negative_rate_high_medium > 0.2}
                />
                <MetricCard label="False Negatives (count)" value={sif.false_negative_count} warn={sif.false_negative_count > 0} />
              </div>

              <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
                <div className="min-w-0">
                  <p className="mb-2 text-[10.5px] font-bold uppercase tracking-wide text-ink_text-muted">Per-class precision / recall / F1</p>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-line text-left text-[10.5px] font-bold uppercase tracking-wide text-ink_text-muted">
                        <th className="py-1.5 pr-2">Class</th>
                        <th className="py-1.5 px-1 text-right">Precision</th>
                        <th className="py-1.5 px-1 text-right">Recall</th>
                        <th className="py-1.5 px-1 text-right">F1</th>
                        <th className="py-1.5 pl-1 text-right">Support</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(sif.per_class).map(([cls, m]) => (
                        <tr key={cls} className="border-b border-line/70">
                          <td className="py-1.5 pr-2 font-bold text-ink_text-primary">{cls}</td>
                          <td className="py-1.5 px-1 text-right tabular-nums">{m.precision}</td>
                          <td className="py-1.5 px-1 text-right tabular-nums">{m.recall}</td>
                          <td className="py-1.5 px-1 text-right tabular-nums">{m.f1}</td>
                          <td className="py-1.5 pl-1 text-right tabular-nums text-ink_text-muted">{m.support}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {sif.confusion_matrix?.labels?.length > 0 && (
                  <div className="min-w-0">
                    <p className="mb-2 text-[10.5px] font-bold uppercase tracking-wide text-ink_text-muted">Confusion matrix (rows=gold, cols=predicted)</p>
                    <div className="overflow-x-auto rounded-xl border border-line bg-surface-muted/40 p-3">
                      <table className="w-full text-sm">
                        <thead>
                          <tr>
                            <th className="px-2 py-1.5 text-left text-[10px] text-ink_text-muted"> </th>
                            {sif.confusion_matrix.labels.map((lab) => (
                              <th key={lab} className="px-2 py-1.5 text-center text-[10px] font-bold text-ink_text-muted">{lab}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {sif.confusion_matrix.matrix.map((row, i) => (
                            <tr key={sif.confusion_matrix.labels[i]}>
                              <td className="px-2 py-1.5 text-[10px] font-bold text-ink_text-muted">{sif.confusion_matrix.labels[i]}</td>
                              {row.map((cell, j) => (
                                <td
                                  key={j}
                                  className={`px-2 py-1.5 text-center tabular-nums font-semibold ${
                                    i === j ? "bg-accent-50 text-accent-800" : "text-ink_text-primary"
                                  }`}
                                >
                                  {cell}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>

              <p className="mt-3.5 text-[11.5px] italic text-ink_text-muted">
                Recall on HIGH/MEDIUM and the false-negative rate are treated as the primary safety metrics — a missed SIF
                precursor is a more serious failure mode than a false alarm. Figures are from the held-out synthetic gold
                split after group-by-base-narrative split hygiene — directional, not OIL production KPIs.
              </p>
            </>
          )}
        </Card>

        <Card className="min-w-0">
          <CardHeader title="IOGP Life-Saving Rule Mapping" icon={<IconList className="h-4 w-4" />} />
          {lsr.insufficient_data ? (
            <p className="text-sm text-ink_text-muted">{lsr.message}</p>
          ) : (
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-[minmax(140px,180px)_1fr]">
              <div className="flex flex-col gap-3">
                <MetricCard label="Test-set cases" value={lsr.n_cases} />
                <MetricCard label="Top-1 Accuracy" value={lsr.top1_accuracy} />
              </div>
              <div className="min-w-0 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line text-left text-[10.5px] font-bold uppercase tracking-wide text-ink_text-muted">
                      <th className="py-1.5 pr-3">Rule</th>
                      <th className="w-24 py-1.5 text-right">Accuracy</th>
                      <th className="w-20 py-1.5 text-right">Support</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(lsr.per_rule).map(([rule, m]) => (
                      <tr key={rule} className="border-b border-line/70">
                        <td className="py-1.5 pr-3">{rule}</td>
                        <td className="py-1.5 text-right tabular-nums">{m.accuracy}</td>
                        <td className="py-1.5 text-right tabular-nums text-ink_text-muted">{m.support}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </Card>
      </div>

      <Card>
        <CardHeader title="Human Review" icon={<IconCheckShield className="h-4 w-4" />} />
        {review.insufficient_data ? (
          <p className="text-sm text-ink_text-muted">{review.message}</p>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <MetricCard label="Total Reviews" value={review.total_reviews} />
            <MetricCard label="Correction Rate" value={review.correction_rate} />
            <MetricCard label="Escalation Rate" value={review.escalation_rate} />
          </div>
        )}
      </Card>
    </div>
  );
}
