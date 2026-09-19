import { useEffect, useState } from "react";
import api, { extractErrorMessage } from "../services/api";
import PageHeader from "../components/PageHeader";
import { LoadingState, ErrorState } from "../components/StateViews";
import { Card, CardHeader } from "../components/ui";
import { IconAlertTriangle, IconBook, IconSparkle } from "../components/icons";

export default function AboutPage() {
  const [kb, setKb] = useState(null);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      const resp = await api.get("/api/catalog/lsr-knowledge-base");
      setKb(resp.data);
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to load LSR knowledge base."));
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div>
      <PageHeader eyebrow="Reference" title="About SIFGuard-OIL" description="Product philosophy, IOGP Life-Saving Rule reference, and known limitations." />

      <Card className="mb-5">
        <CardHeader title="Core Philosophy" icon={<IconSparkle className="h-4 w-4" />} />
        <p className="text-[13.5px] leading-relaxed text-ink_text-secondary">
          "Detect less blindly, explain more clearly." SIFGuard-OIL is an HSE decision-support tool, not a generic AI
          application and not a chatbot. Every classification is traceable to specific evidence in the report text,
          carries a confidence score, and the system is explicitly allowed to abstain ("REVIEW — insufficient
          evidence") rather than force a confident answer. AI supports HSE professionals; it does not autonomously
          make consequential safety decisions.
        </p>
      </Card>

      <Card className="mb-5">
        <CardHeader title="Known Limitations" subtitle="Prototype, honestly stated" icon={<IconAlertTriangle className="h-4 w-4" />} />
        <ul className="space-y-2 text-[13px] leading-relaxed text-ink_text-secondary">
          {[
            <>All demo data is a team-authored <strong>synthetic</strong> dataset grounded in real IOGP/DEKRA-style patterns — not real OIL production data.</>,
            <>Entity extraction, the LSR engine and the barrier-negation engine are deterministic, rule-based systems (not trained NER models) — there is no labelled OIL entity-span corpus to train one on yet. Vocabularies load from <code>precursor_taxonomy.json</code>.</>,
            <>The SIF classifier is trained on a 315-row gold set with <strong>0% train/test base-narrative leakage</strong> (group-level splits); per-class metrics on the smallest classes (LOW, MEDIUM) still carry sampling noise (see the Evaluation page).</>,
            <>The 0-100 risk score and confidence bands are our own prototype design decisions — not an official OIL/IOGP formula.</>,
            <>Site/activity ranking is normalized by report volume, not exposure-hours (not available in this dataset).</>,
            <>The bounded LLM explanation layer is optional and disabled by default; the core pipeline works fully offline.</>,
            <>Reference corpus: <strong>12 REAL_OSHA</strong> citations, <strong>0 REAL_DGMS</strong> (machine-readable DGMS annual-report extracts not available for this prototype), <strong>3 SYNTHETIC_DEMO</strong> India-mining-style illustratives — each comparison shows a provenance badge.</>,
            <>The rule NLP pipeline (entities, barriers, Life-Saving Rules) is <strong>English-only</strong>. Narratives that fail the Latin-token language guard receive <strong>UNSUPPORTED_LANGUAGE</strong>. <strong>Default retrieval embeddings are multilingual</strong> (<code>paraphrase-multilingual-MiniLM-L12-v2</code>); that does not imply multilingual rule extraction. TF-IDF fallback is visible on <code>/health</code> if the ST model fails to load.</>,
            <>Analysis is orchestrated by a real LangGraph pipeline (preprocess → extract → barriers/LSR → fuse → retrieve → explain/persist); each node produces inspectable intermediate state.</>,
          ].map((item, i) => (
            <li key={i} className="flex gap-2">
              <span className="mt-2 h-1 w-1 flex-shrink-0 rounded-full bg-ink_text-muted" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </Card>

      <Card>
        <CardHeader title="IOGP Life-Saving Rules Reference" icon={<IconBook className="h-4 w-4" />} />
        {error && <ErrorState message={error} onRetry={load} />}
        {!error && !kb && <LoadingState label="Loading..." />}
        {!error && kb && (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {kb.map((rule, i) => (
              <div key={rule.rule} className="rounded-xl border border-line p-3.5">
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-md bg-accent-100 text-[11px] font-extrabold text-accent-700">
                    {i + 1}
                  </span>
                  <p className="text-[13px] font-bold text-ink_text-primary">{rule.rule}</p>
                </div>
                <p className="mt-1.5 text-[12px] text-ink_text-secondary">{rule.action}</p>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
