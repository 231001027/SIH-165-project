import { useState, useRef } from "react";
import { Link } from "react-router-dom";
import api, { extractErrorMessage } from "../services/api";
import PageHeader from "../components/PageHeader";
import { Card, Button } from "../components/ui";
import { IconUpload, IconList } from "../components/icons";

const SAMPLE_CSV = `narrative,report_type,title,site,activity,location,occurred_at
"Worker leaned out from a scaffold platform to reach a valve without re-anchoring the fall-arrest lanyard.",NEAR_MISS,Scaffold near miss,Site B (Pipeline Corridor),Working at Height,elevated scaffold platform,
"Toolbox talk was held before the shift and all attendees signed the safety briefing register; no concerns raised.",UNSAFE_CONDITION,Good practice observation,Site A (Upstream E&P),General Maintenance,muster point,`;

export default function UploadPage() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef(null);

  async function handleUpload(e) {
    e.preventDefault();
    if (!file) {
      setError("Choose a .csv file first.");
      return;
    }
    setError("");
    setUploading(true);
    setResult(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const resp = await api.post("/api/reports/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(resp.data);
    } catch (err) {
      setError(extractErrorMessage(err, "Upload failed."));
    } finally {
      setUploading(false);
    }
  }

  function downloadSample() {
    const blob = new Blob([SAMPLE_CSV], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "sifguard_sample_upload.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div>
      <PageHeader
        eyebrow="Ingestion"
        title="CSV Batch Upload"
        description="Upload multiple safety reports at once. Each row is validated, deduplicated and run through the full AI analysis pipeline."
        actions={
          <Button variant="outline" size="md" onClick={downloadSample}>Download sample CSV</Button>
        }
      />

      <Card className="max-w-2xl">
        <p className="mb-4 text-xs text-ink_text-secondary">
          Required column: <code className="rounded bg-surface-muted px-1.5 py-0.5">narrative</code>. Optional columns:{" "}
          <code className="rounded bg-surface-muted px-1.5 py-0.5">report_type, title, site, activity, location, reporter_name, occurred_at</code>.
        </p>
        <form onSubmit={handleUpload} className="space-y-3.5">
          <label
            htmlFor="csv-input"
            className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-line bg-surface-muted/60 px-6 py-8 text-center transition hover:border-accent-300 hover:bg-accent-50/40"
          >
            <IconUpload className="h-6 w-6 text-accent-600" />
            <span className="text-[13px] font-bold text-ink_text-primary">
              {file ? file.name : "Click to choose a .csv file"}
            </span>
            <span className="text-[11px] text-ink_text-muted">or drag and drop</span>
            <input
              id="csv-input"
              ref={inputRef}
              type="file"
              accept=".csv"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="hidden"
            />
          </label>
          {error && <p className="rounded-lg border border-risk-high/20 bg-risk-high/5 px-3 py-2 text-sm font-medium text-risk-high">{error}</p>}
          <Button type="submit" variant="accent" size="lg" disabled={uploading} className="w-full">
            {uploading ? "Uploading and analyzing..." : "Upload and Analyze"}
          </Button>
        </form>
      </Card>

      {result && (
        <div className="mt-6 max-w-3xl">
          <div className="mb-3.5 grid grid-cols-4 gap-3">
            <Card className="text-center">
              <p className="text-xl font-extrabold text-ink_text-primary">{result.total_rows}</p>
              <p className="text-[11px] font-semibold text-ink_text-muted">Total Rows</p>
            </Card>
            <Card className="border-risk-nonsif/20 bg-risk-nonsif/5 text-center">
              <p className="text-xl font-extrabold text-risk-nonsif">{result.successful}</p>
              <p className="text-[11px] font-semibold text-risk-nonsif/80">Successful</p>
            </Card>
            <Card className="border-risk-high/20 bg-risk-high/5 text-center">
              <p className="text-xl font-extrabold text-risk-high">{result.failed}</p>
              <p className="text-[11px] font-semibold text-risk-high/80">Failed</p>
            </Card>
            <Card className="border-risk-low/30 bg-risk-low/5 text-center">
              <p className="text-xl font-extrabold text-[#8a6a10]">{result.duplicates}</p>
              <p className="text-[11px] font-semibold text-[#8a6a10]/80">Duplicates</p>
            </Card>
          </div>
          <Card padded={false} className="overflow-hidden">
            <table className="w-full text-sm">
              <thead className="border-b border-line bg-surface-muted text-left text-[10.5px] font-bold uppercase tracking-wide text-ink_text-muted">
                <tr>
                  <th className="px-3.5 py-2.5">Row</th>
                  <th className="px-3.5 py-2.5">Status</th>
                  <th className="px-3.5 py-2.5">Detail</th>
                </tr>
              </thead>
              <tbody>
                {result.rows.map((r) => (
                  <tr key={r.row_number} className="border-t border-line/70">
                    <td className="px-3.5 py-2">{r.row_number}</td>
                    <td className="px-3.5 py-2">
                      <span
                        className={`rounded-md px-2 py-0.5 text-[11px] font-bold ${
                          r.status === "SUCCESS"
                            ? "bg-risk-nonsif/10 text-risk-nonsif"
                            : r.status === "DUPLICATE"
                            ? "bg-risk-low/10 text-[#8a6a10]"
                            : "bg-risk-high/10 text-risk-high"
                        }`}
                      >
                        {r.status}
                      </span>
                    </td>
                    <td className="px-3.5 py-2 text-ink_text-secondary">
                      {r.status === "SUCCESS" ? (
                        <Link to={`/reports/${r.report_id}`} className="inline-flex items-center gap-1 font-bold text-accent-700 hover:underline">
                          <IconList className="h-3 w-3" /> View report #{r.report_id}
                        </Link>
                      ) : (
                        r.error
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </div>
      )}
    </div>
  );
}
