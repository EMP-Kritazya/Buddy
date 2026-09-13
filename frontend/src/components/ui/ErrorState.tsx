export function ErrorState({
  title = "Something did not load",
  detail,
  onRetry,
}: {
  title?: string;
  detail?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="border border-incident bg-surface px-6 py-10 text-center">
      <p className="font-serif text-[20px] text-ink">{title}</p>
      {detail ? <p className="mt-2 text-[13px] text-ink-2">{detail}</p> : null}
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-5 border border-accent px-4 py-2 text-[13px] text-accent"
        >
          Try again
        </button>
      ) : null}
    </div>
  );
}
