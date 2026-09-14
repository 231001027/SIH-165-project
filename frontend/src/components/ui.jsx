/**
 * Generic UI primitives shared across pages -- the building blocks of the
 * design system (see tailwind.config.js for the underlying color/shadow
 * tokens). Keeping these in one place is what makes 14 pages read as one
 * product instead of 14 independently-styled screens.
 */

export function Card({ children, className = "", padded = true, hover = false }) {
  return (
    <div
      className={`rounded-2xl border border-line bg-surface-raised shadow-card ${
        hover ? "transition hover:-translate-y-0.5 hover:shadow-raised" : ""
      } ${padded ? "p-5" : ""} ${className}`}
    >
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, icon, right }) {
  return (
    <div className="mb-4 flex items-start justify-between gap-3">
      <div className="flex items-start gap-2.5">
        {icon && (
          <span className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-accent-50 text-accent-700">
            {icon}
          </span>
        )}
        <div>
          <p className="text-[13px] font-bold uppercase tracking-wide text-ink_text-primary">{title}</p>
          {subtitle && <p className="mt-0.5 text-xs text-ink_text-muted">{subtitle}</p>}
        </div>
      </div>
      {right}
    </div>
  );
}

const BUTTON_VARIANTS = {
  primary:
    "bg-ink-900 text-white hover:bg-ink-800 shadow-sm disabled:opacity-50 focus-visible:ring-ink-700",
  accent:
    "bg-accent-500 text-ink-950 hover:bg-accent-400 shadow-sm disabled:opacity-50 focus-visible:ring-accent-500 font-semibold",
  outline:
    "border border-line bg-white text-ink_text-primary hover:border-ink-500 hover:bg-surface-muted disabled:opacity-50 focus-visible:ring-ink-500",
  ghost:
    "text-ink_text-secondary hover:bg-surface-muted hover:text-ink_text-primary disabled:opacity-40",
  danger:
    "bg-risk-high text-white hover:brightness-95 shadow-sm disabled:opacity-50 focus-visible:ring-risk-high",
  success:
    "bg-risk-nonsif text-white hover:brightness-95 shadow-sm disabled:opacity-50 focus-visible:ring-risk-nonsif",
};

const BUTTON_SIZES = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
  lg: "px-5 py-2.5 text-sm",
};

export function Button({
  as: Comp = "button",
  variant = "primary",
  size = "md",
  className = "",
  icon,
  children,
  ...props
}) {
  return (
    <Comp
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 ${BUTTON_VARIANTS[variant]} ${BUTTON_SIZES[size]} ${className}`}
      {...props}
    >
      {icon}
      {children}
    </Comp>
  );
}

export function Pill({ children, tone = "neutral", className = "" }) {
  const tones = {
    neutral: "bg-surface-muted text-ink_text-secondary border-line",
    accent: "bg-accent-50 text-accent-700 border-accent-200",
    teal: "bg-teal-50 text-teal-700 border-teal-100",
  };
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${tones[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

export function Divider({ className = "" }) {
  return <div className={`h-px w-full bg-line ${className}`} />;
}

export function Field({ label, value, mono = false }) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-ink_text-muted">{label}</p>
      <p className={`mt-0.5 text-sm font-medium text-ink_text-primary ${mono ? "font-mono" : ""}`}>
        {value ?? "—"}
      </p>
    </div>
  );
}

export function Label({ children }) {
  return <label className="mb-1.5 block text-xs font-semibold text-ink_text-secondary">{children}</label>;
}

export function Input(props) {
  return (
    <input
      {...props}
      className={`w-full rounded-lg border border-line bg-white px-3 py-2 text-sm text-ink_text-primary placeholder:text-ink_text-muted transition focus:border-accent-500 focus:outline-none focus:ring-2 focus:ring-accent-100 ${props.className || ""}`}
    />
  );
}

export function Select(props) {
  return (
    <select
      {...props}
      className={`rounded-lg border border-line bg-white px-3 py-2 text-sm text-ink_text-primary transition focus:border-accent-500 focus:outline-none focus:ring-2 focus:ring-accent-100 ${props.className || ""}`}
    />
  );
}

export function Textarea(props) {
  return (
    <textarea
      {...props}
      className={`w-full rounded-lg border border-line bg-white px-3 py-2 text-sm text-ink_text-primary placeholder:text-ink_text-muted transition focus:border-accent-500 focus:outline-none focus:ring-2 focus:ring-accent-100 ${props.className || ""}`}
    />
  );
}
