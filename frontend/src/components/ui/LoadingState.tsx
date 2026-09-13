export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div className="border border-border-2 bg-surface px-6 py-10 text-center">
      <p className="font-mono text-[11px] text-ink-2">{label}…</p>
    </div>
  );
}
