import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { extractErrorMessage } from "../services/api";
import PageHeader from "../components/PageHeader";
import { Card, Button, Input, Select, Textarea, Label } from "../components/ui";
import { IconSparkle } from "../components/icons";

const DEMO_NARRATIVE =
  "Technician opened a flange before confirming isolation. Residual pressure was released. No injury occurred.";

export default function NewReportPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    report_type: "NEAR_MISS",
    title: "",
    narrative: "",
    site: "",
    activity: "",
    location: "",
    reporter_name: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  function setField(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (!form.narrative.trim()) {
      setError("The report narrative is required.");
      return;
    }
    setSubmitting(true);
    try {
      const resp = await api.post("/api/reports", form);
      navigate(`/reports/${resp.data.id}`);
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to submit report."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Ingestion"
        title="Submit a Safety Report"
        description="Enter a free-text UA/UC, near-miss or incident narrative. The AI pipeline analyzes English narratives immediately after submission. Non-English / Devanagari text is flagged UNSUPPORTED_LANGUAGE for manual review."
      />

      <div className="mb-4 max-w-2xl rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-[13px] text-amber-950">
        <p className="font-bold">English-language narratives only (prototype)</p>
        <p className="mt-1 leading-relaxed text-amber-900/90">
          The rule-based analysis pipeline currently requires predominantly ASCII Latin text.
          Devanagari or other non-English scripts are not analyzed automatically — you will see an
          explicit <span className="font-semibold">Unsupported language</span> status and a manual-review
          requirement instead of a silent wrong SIF band.
        </p>
      </div>

      <Card className="max-w-2xl">
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && <p className="rounded-lg border border-risk-high/20 bg-risk-high/5 px-3 py-2 text-sm font-medium text-risk-high">{error}</p>}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Report Type</Label>
              <Select value={form.report_type} onChange={(e) => setField("report_type", e.target.value)} className="w-full">
                <option value="UNSAFE_ACT">Unsafe Act</option>
                <option value="UNSAFE_CONDITION">Unsafe Condition</option>
                <option value="NEAR_MISS">Near Miss</option>
                <option value="INCIDENT">Incident</option>
              </Select>
            </div>
            <div>
              <Label>Title (optional)</Label>
              <Input type="text" value={form.title} onChange={(e) => setField("title", e.target.value)} />
            </div>
          </div>

          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <Label>Narrative *</Label>
              <button
                type="button"
                onClick={() => setField("narrative", DEMO_NARRATIVE)}
                className="inline-flex items-center gap-1 text-xs font-bold text-accent-700 hover:underline"
              >
                <IconSparkle className="h-3 w-3" /> Use flagship demo scenario
              </button>
            </div>
            <Textarea
              required
              rows={5}
              value={form.narrative}
              onChange={(e) => setField("narrative", e.target.value)}
              placeholder="Describe what happened in free text, as a field worker or HSE observer would write it..."
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Site</Label>
              <Input type="text" value={form.site} onChange={(e) => setField("site", e.target.value)} placeholder="e.g. Site A (Upstream E&P)" />
            </div>
            <div>
              <Label>Activity</Label>
              <Input type="text" value={form.activity} onChange={(e) => setField("activity", e.target.value)} placeholder="e.g. Pipeline Maintenance" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Location</Label>
              <Input type="text" value={form.location} onChange={(e) => setField("location", e.target.value)} />
            </div>
            <div>
              <Label>Reporter</Label>
              <Input type="text" value={form.reporter_name} onChange={(e) => setField("reporter_name", e.target.value)} />
            </div>
          </div>

          <Button type="submit" variant="accent" size="lg" disabled={submitting} className="w-full">
            {submitting ? "Analyzing with SIFGuard-OIL AI pipeline..." : "Submit and Analyze"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
