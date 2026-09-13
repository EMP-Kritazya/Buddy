import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";

type AuthPageLayoutProps = {
  statement: ReactNode;
  children: ReactNode;
};

export function AuthPageLayout({ statement, children }: AuthPageLayoutProps) {
  return (
    <div className="min-h-screen bg-canvas text-ink lg:grid lg:grid-cols-2">
      <aside className="hidden min-h-[200px] flex-col justify-between bg-ink px-12 py-10 md:flex lg:min-h-screen lg:py-[60px]">
        <Link to="/" className="self-start font-serif text-[22px] text-canvas">
          Buddy
        </Link>

        <div className="my-10 lg:my-auto">
          <p className="max-w-[320px] font-serif text-[36px] font-normal italic leading-[1.3] text-canvas">
            {statement}
          </p>

          <div className="mt-10 hidden max-w-[280px] rounded-[4px] bg-plot-grid p-5 lg:block">
            <div className="mb-4 flex items-center gap-1.5 font-mono text-[10px] text-accent">
              <span className="buddy-pulse size-1.5 rounded-full bg-accent" aria-hidden="true" />
              <span>Active</span>
            </div>
            <div className="grid grid-cols-2 gap-5">
              <div>
                <p className="font-mono text-[28px] leading-none text-canvas">84</p>
                <p className="mt-1.5 text-[11px] text-ink-2">Live score</p>
              </div>
              <div>
                <p className="text-[13px] font-medium text-canvas">VS Code</p>
                <p className="mt-1.5 text-[11px] text-ink-2">Current app</p>
              </div>
            </div>
          </div>
        </div>

        <p className="hidden font-mono text-[10px] text-ink-2 lg:block">Built at HackRice 16 · Sep 2026</p>
      </aside>

      <main className="flex min-h-screen flex-col justify-center bg-canvas px-6 py-10 md:px-12 md:py-[60px] lg:px-12">
        <div className="w-full max-w-[400px] lg:mx-auto">
          <Link to="/" className="mb-12 block font-serif text-xl text-ink md:hidden">
            Buddy
          </Link>
          {children}
        </div>
      </main>
    </div>
  );
}

type AuthFieldProps = {
  id: string;
  label: string;
  type: "text" | "email" | "password";
  placeholder: string;
  value: string;
  error?: string | undefined;
  autoComplete: string;
  hint?: ReactNode;
  onChange: (value: string) => void;
};

export function AuthField({
  id,
  label,
  type,
  placeholder,
  value,
  error,
  autoComplete,
  hint,
  onChange,
}: AuthFieldProps) {
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ") || undefined;

  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-xs font-medium text-ink-2">
        {label}
      </label>
      <input
        id={id}
        name={id}
        type={type}
        value={value}
        placeholder={placeholder}
        autoComplete={autoComplete}
        aria-invalid={Boolean(error)}
        aria-describedby={describedBy}
        onChange={(event) => onChange(event.target.value)}
        className={`w-full rounded-none border-0 border-b bg-transparent px-0 py-2.5 font-sans text-[15px] text-ink outline-none transition-colors duration-150 placeholder:text-border focus:border-accent focus:ring-0 ${
          error ? "border-incident" : "border-border"
        }`}
      />
      {hint ? (
        <div id={hintId} className="mt-1.5 text-[11px] text-ink-3">
          {hint}
        </div>
      ) : null}
      {error ? (
        <p id={errorId} className="mt-1.5 text-xs text-incident" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}