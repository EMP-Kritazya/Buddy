export interface WaitingStateProps {
  message: string;
  submessage?: string | undefined;
  /** "pulse" = amber dot + message, "text" = single quiet line, "reflective" = Newsreader italic. */
  variant?: "pulse" | "text" | "reflective";
  /** "light" for use on the dark chart background. */
  tone?: "dark" | "light";
  className?: string;
}

export function WaitingState({
  message,
  submessage,
  variant = "pulse",
  tone = "dark",
  className = "",
}: WaitingStateProps) {
  if (variant === "text") {
    return <p className={`py-3 text-[14px] text-ink-3 ${className}`}>{message}</p>;
  }

  if (variant === "reflective") {
    return (
      <div className={`buddy-waiting-in py-8 text-center ${className}`}>
        <p className="mb-2 font-serif text-[20px] italic text-ink-3">{message}</p>
        {submessage ? <p className="text-[13px] leading-[1.5] text-ink-3">{submessage}</p> : null}
      </div>
    );
  }

  return (
    <div
      className={`buddy-waiting-in flex min-h-[200px] flex-col items-center justify-center px-6 py-12 text-center ${className}`}
    >
      <span className="buddy-pulse mb-5 size-[10px] rounded-full bg-drift" />
      <p className={`mb-1.5 text-[15px] ${tone === "light" ? "text-canvas" : "text-ink-2"}`}>{message}</p>
      {submessage ? (
        <p className={`font-mono text-[12px] ${tone === "light" ? "text-ink-2" : "text-ink-3"}`}>{submessage}</p>
      ) : null}
    </div>
  );
}
