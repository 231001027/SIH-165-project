import { IconExternal } from "./icons";

// Canonical SIF-risk colors -- kept in sync with tailwind.config.js `risk.*`
// tokens. Never remap these hues to a different meaning elsewhere in the app.
const SIF_STYLES = {
  HIGH: "bg-risk-high/10 text-risk-high border-risk-high/25",
  MEDIUM: "bg-risk-medium/10 text-risk-medium border-risk-medium/25",
  LOW: "bg-risk-low/10 text-[#8a6a10] border-risk-low/30",
  NON_SIF: "bg-risk-nonsif/10 text-risk-nonsif border-risk-nonsif/25",
  REVIEW: "bg-risk-review/10 text-risk-review border-risk-review/25",
  UNSUPPORTED_LANGUAGE: "bg-amber-50 text-amber-900 border-amber-300",
};

const SIF_DOT = {
  HIGH: "bg-risk-high",
  MEDIUM: "bg-risk-medium",
  LOW: "bg-risk-low",
  NON_SIF: "bg-risk-nonsif",
  REVIEW: "bg-risk-review",
  UNSUPPORTED_LANGUAGE: "bg-amber-600",
};

export function SifBadge({ value, size = "md", pulse = false }) {
  const style = SIF_STYLES[value] || "bg-surface-muted text-ink_text-secondary border-line";
  const sizeClass = size === "lg" ? "text-[13px] px-3 py-1" : "text-[11px] px-2 py-0.5";
  const label =
    value === "NON_SIF" ? "NON-SIF"
    : value === "UNSUPPORTED_LANGUAGE" ? "UNSUPPORTED LANGUAGE"
    : value;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-bold tracking-wide ${style} ${sizeClass}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${SIF_DOT[value] || "bg-ink_text-muted"} ${pulse ? "animate-pulse-ring" : ""}`} />
      {label}
    </span>
  );
}

export function UnsupportedLanguageBanner({ message }) {
  return (
    <div
      role="status"
      className="rounded-xl border-2 border-amber-400 bg-amber-50 px-4 py-3 text-[13.5px] leading-relaxed text-amber-950"
    >
      <p className="font-extrabold tracking-wide text-amber-900">Unsupported language / script</p>
      <p className="mt-1 font-medium">
        {message
          || "This prototype currently supports English-language input only. Automated analysis was not run for this report; manual review is required."}
      </p>
    </div>
  );
}

const BARRIER_STYLES = {
  PRESENT_EFFECTIVE: "bg-risk-nonsif/10 text-risk-nonsif border-risk-nonsif/25",
  NOT_VERIFIED: "bg-risk-low/10 text-[#8a6a10] border-risk-low/30",
  UNKNOWN: "bg-surface-muted text-ink_text-secondary border-line",
  MISSING: "bg-risk-medium/10 text-risk-medium border-risk-medium/25",
  BYPASSED: "bg-risk-high/10 text-risk-high border-risk-high/25",
  FAILED: "bg-risk-high/10 text-risk-high border-risk-high/25",
};

export function BarrierStatusBadge({ value }) {
  const style = BARRIER_STYLES[value] || "bg-surface-muted text-ink_text-secondary border-line";
  return (
    <span className={`inline-block rounded-md border px-2 py-0.5 text-[11px] font-semibold ${style}`}>
      {value?.replace(/_/g, " ")}
    </span>
  );
}

export function SyntheticBadge() {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-md border border-teal-100 bg-teal-50 px-2 py-0.5 text-[10.5px] font-semibold text-teal-700"
      title="This record is from the team-authored synthetic demo dataset, not real OIL production data."
    >
      Synthetic demo data
    </span>
  );
}

export function ReferenceIncidentBadge({ url }) {
  const content = (
    <span
      className="inline-flex items-center gap-1 rounded-md border border-accent-200 bg-accent-50 px-2 py-0.5 text-[10.5px] font-semibold text-accent-700"
      title="A real, independently-verifiable historical incident used only to ground similarity search -- not OIL data."
    >
      Real historical incident
      {url && <IconExternal className="h-3 w-3" />}
    </span>
  );
  return url ? (
    <a href={url} target="_blank" rel="noreferrer">
      {content}
    </a>
  ) : (
    content
  );
}

export function ReportTypeBadge({ value }) {
  return (
    <span className="inline-block rounded-md border border-line bg-surface-muted px-2 py-0.5 text-[11px] font-semibold text-ink_text-secondary">
      {value?.replace(/_/g, " ")}
    </span>
  );
}

export function ReasonCodeChip({ code }) {
  return (
    <span className="inline-block rounded-full bg-ink-900/[0.05] px-2.5 py-0.5 text-[11px] font-semibold text-ink-800">
      {code.replace(/_/g, " ")}
    </span>
  );
}
