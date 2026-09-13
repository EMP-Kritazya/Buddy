import { Link, useNavigate } from "@tanstack/react-router";
import { CheckCircle, Download } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";

const agentDetails = [
  ["Watches", "Logs the active app and window title every 30 seconds."],
  ["Scores", "Sends data to Buddy's backend. Never uploads your screen content."],
  ["Triggers", "Alerts your wearable when focus drops below your threshold."],
] as const;

export default function DownloadPage() {
  const navigate = useNavigate();
  const [isReady, setIsReady] = useState(false);

  return (
    <main className="min-h-screen bg-canvas px-5 py-10 text-ink sm:px-8 md:px-12 md:py-20">
      <div className="mx-auto max-w-[640px]">
        <header className="flex items-center justify-between border-b border-border pb-5">
          <Link to="/" className="font-serif text-xl text-ink">
            Buddy
          </Link>
          <p className="font-mono text-xs text-ink-3">Step 2 of 3</p>
        </header>

        <div className="mb-[60px] mt-[60px] h-0.5 w-full bg-border-2" aria-hidden="true">
          <div className="h-full w-2/3 bg-accent" />
        </div>

        <section>
          <p className="mb-6 font-mono text-[11px] tracking-[0.08em] text-ink-3">Get the agent</p>
          <h1 className="mb-4 font-serif text-[36px] font-normal leading-[1.15] text-ink md:text-[44px]">
            Install Buddy on
            <br />
            your computer.
          </h1>
          <p className="mb-12 max-w-[440px] text-[15px] leading-[1.65] text-ink-2">
            A small background app that watches what you're working on. It runs silently and uses
            almost no resources.
          </p>

          <Button
            type="button"
            onClick={() => setIsReady(true)}
            className="h-auto w-full justify-start rounded-[3px] bg-ink px-7 py-3.5 text-left text-canvas shadow-none hover:bg-plot-grid sm:w-fit"
          >
            <Download className="size-4" aria-hidden="true" />
            <span className="flex flex-col items-start">
              <span className="text-sm font-medium">Download Buddy Agent</span>
              <span className="font-mono text-[10px] font-normal text-ink-3">
                Windows · macOS · Linux
              </span>
            </span>
          </Button>

          {isReady ? (
            <p className="buddy-download-confirm mt-4 flex items-center gap-1.5 font-mono text-xs text-accent" role="status">
              <CheckCircle className="size-4" aria-hidden="true" />
              buddy-agent-v1.0.exe is ready.
            </p>
          ) : null}

          <div className="mt-12 border-t border-border pt-8">
            <p className="mb-5 font-mono text-[11px] text-ink-3">What the agent does</p>
            <dl>
              {agentDetails.map(([tag, description]) => (
                <div key={tag} className="flex gap-4 border-b border-border-2 py-3">
                  <dt className="w-[64px] shrink-0 font-mono text-[11px] text-ink-3">{tag}</dt>
                  <dd className="text-sm leading-[1.5] text-ink-2">{description}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        <nav className="mt-12 flex items-start justify-between gap-6">
          <Link to="/onboarding" className="py-2.5 text-[13px] text-ink-3 transition-colors hover:text-ink">
            ← Back
          </Link>
          <div className="text-right">
            <Button
              type="button"
              onClick={() => void navigate({ to: "/connect" })}
              className="h-auto rounded-[3px] bg-accent px-6 py-2.5 text-sm font-medium text-surface shadow-none hover:bg-accent hover:brightness-90"
            >
              Continue →
            </Button>
            <p className="mt-2 text-[11px] text-ink-3">You can also install this later.</p>
          </div>
        </nav>
      </div>
    </main>
  );
}
