import { Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

type ConnectionState = "searching" | "connected";

export default function ConnectPage() {
  const navigate = useNavigate();
  const [connectionState, setConnectionState] = useState<ConnectionState>("searching");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    const delay = 5000 + Math.random() * 10000;
    const connectionTimer = window.setTimeout(() => setConnectionState("connected"), delay);
    const elapsedTimer = window.setInterval(() => {
      setElapsedSeconds((seconds) => seconds + 1);
    }, 1000);

    return () => {
      window.clearTimeout(connectionTimer);
      window.clearInterval(elapsedTimer);
    };
  }, []);

  return (
    <main className="min-h-screen bg-canvas px-5 py-10 text-ink sm:px-8 md:px-12 md:py-20">
      <div className="mx-auto max-w-[640px]">
        <header className="flex items-center justify-between border-b border-border pb-5">
          <Link to="/" className="font-serif text-xl text-ink">
            Buddy
          </Link>
          <p className="font-mono text-xs text-ink-3">Step 3 of 3</p>
        </header>

        <div className="mb-[60px] mt-[60px] h-0.5 w-full bg-border-2" aria-hidden="true">
          <div className="h-full w-full bg-accent" />
        </div>

        <section>
          <p className="mb-6 font-mono text-[11px] tracking-[0.08em] text-ink-3">Wearable</p>
          <h1 className="mb-4 font-serif text-[36px] font-normal leading-[1.15] text-ink md:text-[44px]">
            Connecting to your
            <br />
            Buddy Wearable.
          </h1>
          <p className="mb-14 max-w-[420px] text-[15px] leading-[1.65] text-ink-2">
            Make sure your wearable is powered on and within range. This usually takes a few
            seconds.
          </p>

          <div className="min-h-[245px] max-w-[380px]" aria-live="polite">
            {connectionState === "searching" ? (
              <div className="buddy-connect-fade">
                <div className="mb-8 flex items-center gap-2.5 font-mono text-[13px] text-drift">
                  <span className="buddy-scan-dot size-2.5 rounded-full bg-drift" aria-hidden="true" />
                  <span>Searching for devices...</span>
                </div>
                <p className="mb-2 text-lg font-medium text-ink-3">Buddy Wearable</p>
                <p className="mb-8 font-mono text-[11px] text-ink-3">ESP32-S3 · Wi-Fi</p>
                <div className="relative h-0.5 overflow-hidden bg-border-2" aria-hidden="true">
                  <span className="buddy-scan-sweep absolute inset-y-0 left-0 w-[30%]" />
                </div>
                <p className="mt-2 font-mono text-[11px] text-ink-3">
                  Scanning · {elapsedSeconds}s
                </p>
              </div>
            ) : (
              <div className="buddy-connect-fade">
                <div className="mb-8 flex items-center gap-2.5 font-mono text-[13px] text-accent">
                  <span className="size-2 rounded-full bg-accent" aria-hidden="true" />
                  <span>Connected</span>
                </div>
                <p className="mb-2 text-lg font-medium text-ink">Buddy Wearable</p>
                <p className="mb-8 font-mono text-[11px] text-ink-3">ESP32-S3 · Wi-Fi</p>

                <div className="mt-8">
                  <p className="mb-2 text-base font-medium text-ink">Buddy Wearable is ready.</p>
                  <p className="text-sm text-ink-2">
                    You'll hear a confirmation tone through the speaker.
                  </p>
                </div>
              </div>
            )}
          </div>
        </section>

        <nav className="mt-12 flex items-start justify-between gap-6">
          <Link to="/download" className="py-2.5 text-[13px] text-ink-3 transition-colors hover:text-ink">
            ← Back
          </Link>
          <div className="text-right">
            <Button
              type="button"
              variant={connectionState === "connected" ? "default" : "outline"}
              onClick={() => void navigate({ to: "/dashboard" })}
              className={`h-auto rounded-[3px] px-6 py-2.5 text-sm shadow-none transition-[background-color,color,border-color] duration-300 ${
                connectionState === "connected"
                  ? "border-accent bg-accent font-medium text-surface hover:bg-accent hover:brightness-90"
                  : "border-border bg-transparent font-normal text-ink-3 hover:bg-transparent hover:text-ink"
              }`}
            >
              Go to dashboard →
            </Button>
            {connectionState === "searching" ? (
              <p className="mt-2 text-[11px] text-ink-3">Skip — connect wearable later</p>
            ) : null}
          </div>
        </nav>
      </div>
    </main>
  );
}
