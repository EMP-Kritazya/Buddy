export function EmptyState({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <div className="border border-border-2 bg-surface px-6 py-10 text-center">
      <p className="font-serif text-[20px] text-ink">{title}</p>
      {description ? <p className="mt-2 text-[13px] text-ink-3">{description}</p> : null}
    </div>
  );
}
