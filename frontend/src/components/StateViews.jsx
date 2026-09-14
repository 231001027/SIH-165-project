import { IconAlertTriangle } from "./icons";

export function LoadingState({ label = "Loading..." }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-ink_text-muted">
      <div className="relative h-9 w-9">
        <div className="absolute inset-0 animate-spin rounded-full border-[3px] border-accent-100 border-t-accent-500" />
      </div>
      <span className="text-sm font-medium">{label}</span>
    </div>
  );
}

export function ErrorState({ message = "Something went wrong.", onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-risk-high/20 bg-risk-high/5 py-14 text-center">
      <span className="flex h-10 w-10 items-center justify-center rounded-full bg-risk-high/10 text-risk-high">
        <IconAlertTriangle className="h-5 w-5" />
      </span>
      <p className="max-w-sm text-sm font-medium text-ink_text-primary">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="rounded-lg bg-ink-900 px-4 py-1.5 text-sm font-semibold text-white transition hover:bg-ink-800"
        >
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title = "Nothing here yet", description, action, icon }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-line bg-surface-raised py-16 text-center">
      {icon && (
        <span className="mb-1 flex h-11 w-11 items-center justify-center rounded-full bg-surface-muted text-ink_text-muted">
          {icon}
        </span>
      )}
      <p className="text-[15px] font-bold text-ink_text-primary">{title}</p>
      {description && <p className="max-w-md text-[13px] text-ink_text-secondary">{description}</p>}
      {action}
    </div>
  );
}
