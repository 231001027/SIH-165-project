export default function PageHeader({ eyebrow, title, description, actions }) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4 border-b border-line pb-5">
      <div>
        {eyebrow && (
          <p className="mb-1.5 text-[11px] font-bold uppercase tracking-[0.14em] text-accent-600">
            {eyebrow}
          </p>
        )}
        <h1 className="text-[22px] font-extrabold tracking-tight text-ink_text-primary">{title}</h1>
        {description && <p className="mt-1.5 max-w-2xl text-[13.5px] leading-relaxed text-ink_text-secondary">{description}</p>}
      </div>
      {actions && <div className="flex flex-shrink-0 flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
