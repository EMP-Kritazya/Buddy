export function PagePlaceholder({ name }: { name: string }) {
  return (
    <div className="flex min-h-[70vh] items-center justify-center">
      <h1 className="font-serif text-[32px] font-normal text-ink">{name} — coming next</h1>
    </div>
  );
}
