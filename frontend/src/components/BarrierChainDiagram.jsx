import { IconChevronRight, IconDrop, IconBolt, IconFlame, IconAlertTriangle } from "./icons";
import { BarrierStatusBadge } from "./Badges";

const BARRIER_TONE = {
  PRESENT_EFFECTIVE: { ring: "ring-risk-nonsif/30", bg: "bg-risk-nonsif/5", dot: "bg-risk-nonsif" },
  NOT_VERIFIED: { ring: "ring-risk-low/40", bg: "bg-risk-low/5", dot: "bg-risk-low" },
  UNKNOWN: { ring: "ring-line", bg: "bg-surface-muted", dot: "bg-ink_text-muted" },
  MISSING: { ring: "ring-risk-medium/40", bg: "bg-risk-medium/5", dot: "bg-risk-medium" },
  BYPASSED: { ring: "ring-risk-high/40", bg: "bg-risk-high/5", dot: "bg-risk-high" },
  FAILED: { ring: "ring-risk-high/40", bg: "bg-risk-high/5", dot: "bg-risk-high" },
};

function Node({ eyebrow, title, subtitle, icon, tone = "default" }) {
  const toneClass =
    tone === "danger"
      ? "border-risk-high/30 bg-risk-high/5"
      : tone === "muted"
      ? "border-line bg-surface-muted"
      : "border-line bg-white";
  return (
    <div className={`flex min-w-[148px] flex-1 flex-col gap-1 rounded-xl border ${toneClass} px-3.5 py-3 shadow-sm`}>
      <div className="flex items-center gap-1.5 text-ink_text-muted">
        {icon}
        <span className="text-[10px] font-bold uppercase tracking-wide">{eyebrow}</span>
      </div>
      <p className="text-[13px] font-bold leading-snug text-ink_text-primary">{title || "Not detected"}</p>
      {subtitle && <p className="text-[11px] leading-snug text-ink_text-secondary">{subtitle}</p>}
    </div>
  );
}

function Arrow() {
  return (
    <div className="flex flex-shrink-0 items-center justify-center px-0.5 text-ink_text-muted/60">
      <IconChevronRight className="h-4 w-4" />
    </div>
  );
}

/**
 * Renders the Hazard -> Energy -> Exposure -> Barrier(s) -> Consequence causal
 * chain for one analyzed report (blueprint Part 6.1 "Barrier failure graph,
 * per-incident chain view"). This is the same fields already computed by the
 * pipeline (AnalysisResult) -- purely a visualization, no new backend logic.
 */
export default function BarrierChainDiagram({ hazard, energySource, exposureProximity, exposureDescription, barriers, potentialConsequence }) {
  const worstBarrier =
    barriers && barriers.length > 0
      ? barriers.reduce((worst, b) => {
          const rank = { PRESENT_EFFECTIVE: 0, NOT_VERIFIED: 2, UNKNOWN: 2, MISSING: 3, BYPASSED: 4, FAILED: 4 };
          return (rank[b.status] ?? 1) >= (rank[worst.status] ?? 1) ? b : worst;
        }, barriers[0])
      : null;
  const consequenceIsSevere = /serious|fatal/i.test(potentialConsequence || "");

  return (
    <div className="space-y-3">
      <div className="flex flex-col items-stretch gap-1.5 sm:flex-row sm:items-center">
        <Node eyebrow="Hazard" title={hazard} icon={<IconFlame className="h-3.5 w-3.5" />} />
        <Arrow />
        <Node eyebrow="Energy source" title={energySource} icon={<IconBolt className="h-3.5 w-3.5" />} />
        <Arrow />
        <Node
          eyebrow="Worker exposure"
          title={exposureProximity && exposureProximity !== "NONE" ? `${exposureProximity} proximity` : "No exposure detected"}
          subtitle={exposureDescription}
          icon={<IconDrop className="h-3.5 w-3.5" />}
        />
        <Arrow />
        <div className="flex min-w-[160px] flex-1 flex-col gap-1.5">
          {barriers && barriers.length > 0 ? (
            barriers.map((b, i) => {
              const tone = BARRIER_TONE[b.status] || BARRIER_TONE.UNKNOWN;
              return (
                <div key={i} className={`flex items-center justify-between gap-2 rounded-xl border border-line ${tone.bg} px-3 py-2 ring-1 ${tone.ring}`}>
                  <div className="flex min-w-0 items-center gap-2">
                    <span className={`h-2 w-2 flex-shrink-0 rounded-full ${tone.dot}`} />
                    <span className="truncate text-[12.5px] font-bold text-ink_text-primary">{b.barrier_type}</span>
                  </div>
                  <BarrierStatusBadge value={b.status} />
                </div>
              );
            })
          ) : (
            <Node eyebrow="Barrier" title="None mentioned" tone="muted" />
          )}
        </div>
        <Arrow />
        <Node
          eyebrow="Potential consequence"
          title={potentialConsequence}
          icon={<IconAlertTriangle className="h-3.5 w-3.5" />}
          tone={consequenceIsSevere ? "danger" : "default"}
        />
      </div>
      {worstBarrier && worstBarrier.evidence_text && (
        <p className="rounded-lg bg-surface-muted px-3 py-2 text-[11.5px] italic leading-relaxed text-ink_text-secondary">
          Evidence for {worstBarrier.barrier_type}: "{worstBarrier.evidence_text}"
        </p>
      )}
    </div>
  );
}
