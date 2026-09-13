import { Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import wearableAsset from "@/assets/wearable.webp.asset.json";

function HeroBackground() {
  const [points, setPoints] = useState<number[]>(Array(80).fill(0.75));
  const [currentScore, setCurrentScore] = useState(0.75);
  const [prevScore, setPrevScore] = useState(0.75);

  useEffect(() => {
    let score = 0.75;
    let stepCount = 0;

    const interval = setInterval(() => {
      stepCount++;
      setPrevScore(score);

      const noise = (Math.random() - 0.48) * 0.03;
      const meanReversion = (0.65 - score) * 0.02;
      score = Math.max(0.05, Math.min(0.98, score + noise + meanReversion));

      if (stepCount % 180 === 0) {
        score = 0.15 + Math.random() * 0.2;
      }
      if (stepCount % 180 === 60) {
        score = 0.7 + Math.random() * 0.2;
      }

      setCurrentScore(score);
      setPoints((prev) => [...prev.slice(1), score]);
    }, 80);

    return () => clearInterval(interval);
  }, []);

  const width = 1440;
  const height = 300;
  const padding = { left: 40, right: 20, top: 20, bottom: 20 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;

  const pointsStr = points
    .map((score, i) => {
      const x = padding.left + (i / (points.length - 1)) * plotWidth;
      const y = padding.top + (1 - score) * plotHeight;
      return `${x},${y}`;
    })
    .join(" ");

  const lastScore = points[points.length - 1] ?? 0.75;
  const lastX = padding.left + plotWidth;
  const lastY = padding.top + (1 - lastScore) * plotHeight;

  const direction = currentScore > prevScore ? "up" : currentScore < prevScore ? "down" : "stable";

  const lineColor = lastScore > 0.7 ? "#3F6B5B" : lastScore > 0.5 ? "#C9852C" : "#C45A4A";

  const tipColor = direction === "up" ? "#3F6B5B" : direction === "down" ? "#C45A4A" : "#C9852C";

  const tipArrow = direction === "up" ? "↑" : direction === "down" ? "↓" : "→";

  const displayScore = Math.round(lastScore * 100);
  const tipYPercent = (1 - lastScore) * 100;

  return (
    <>
      <svg
        aria-hidden="true"
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          opacity: 0.18,
          pointerEvents: "none",
        }}
      >
        <defs>
          <linearGradient id="fadeLeft" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#F7F5EF" stopOpacity="1" />
            <stop offset="12%" stopColor="#F7F5EF" stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Y-axis line */}
        <line
          x1={padding.left}
          y1={padding.top}
          x2={padding.left}
          y2={padding.top + plotHeight}
          stroke="#1F2933"
          strokeWidth="0.5"
          opacity="0.4"
        />

        {/* Y-axis ticks */}
        {[1.0, 0.5, 0.0].map((val) => {
          const y = padding.top + (1 - val) * plotHeight;
          return (
            <g key={val}>
              <line
                x1={padding.left - 4}
                y1={y}
                x2={padding.left}
                y2={y}
                stroke="#1F2933"
                strokeWidth="0.5"
                opacity="0.4"
              />
              <text
                x={padding.left - 6}
                y={y + 3}
                textAnchor="end"
                fontSize="8"
                fontFamily="'Geist Mono', monospace"
                fill="#1F2933"
                opacity="1"
              >
                {val.toFixed(1)}
              </text>
            </g>
          );
        })}

        {/* The line */}
        <polyline
          points={pointsStr}
          fill="none"
          stroke={lineColor}
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Tip dot */}
        <circle cx={lastX} cy={lastY} r="5" fill={tipColor} />

        {/* Fade left overlay */}
        <rect x="0" y="0" width={width} height={height} fill="url(#fadeLeft)" />
      </svg>

      {/* Live tip tooltip — outside SVG */}
      <div
        style={{
          position: "absolute",
          left: "calc(100% - 80px)",
          top: `${tipYPercent}%`,
          transform: "translateY(-50%)",
          zIndex: 10,
          background: "rgba(31,41,51,0.85)",
          borderRadius: "3px",
          padding: "4px 10px",
          fontFamily: "Geist Mono",
          fontSize: "11px",
          color: tipColor,
          pointerEvents: "none",
          whiteSpace: "nowrap",
        }}
      >
        {tipArrow} {displayScore}%
      </div>

      {/* Y-axis label — outside SVG */}
      <div
        style={{
          position: "absolute",
          left: 8,
          top: "50%",
          transform: "translateY(-50%) rotate(-90deg)",
          transformOrigin: "center center",
          fontFamily: "Geist Mono",
          fontSize: "9px",
          color: "rgba(31,41,51,0.4)",
          pointerEvents: "none",
          whiteSpace: "nowrap",
          zIndex: 10,
        }}
      >
        Productivity Score
      </div>
    </>
  );
}

const steps = [
  ["01", "Create account", "Takes 60 seconds."],
  ["02", "Tell Buddy about you", "Goals, schedule, distractions."],
  ["03", "Install Buddy", "One small background app."],
  ["04", "Connect your wearable", "Automatic pairing."],
  ["05", "See your first score", "In under a minute."],
];

const processRows = [
  {
    number: "01",
    title: "Tell Buddy your goals",
    description:
      "Speak them before you start. Buddy stores them and uses them all day to understand what counts as focus.",
    tag: "Voice · ElevenLabs",
  },
  {
    number: "02",
    title: "Work like normal",
    description:
      "Buddy watches your computer usage silently. For any app active on your machine, it scores your activity against your goals — no setup, no tagging.",
    tag: "PC Agent · MATLAB",
  },
  {
    number: "03",
    title: "Productivity drops? Buddy notices.",
    description:
      "When your productivity drops and holds low, a calm voice through your wrist brings you back. Not a notification. Not a popup. A companion.",
    tag: "Gemini · Wearable",
  },
];

const signals = [
  ["What you're working on", "The exact application and window active on your machine, tracked continuously in the background."],
  ["How focused you've been", "A live score from 0 to 1 — where 0.5 is neutral, below is unproductive, and towards 1 is increasingly productive. Plotted across your entire day."],
  ["The exact moment you drifted", "Timestamped, annotated, and marked directly on your daily chart."],
  ["A journal written for you", "At the end of every day, Buddy writes a clear record of how your attention moved."],
];

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <p className="font-mono text-[11px] tracking-[0.08em] text-ink-3">{children}</p>;
}

export default function LandingPage() {
  const scrollToHowItWorks = () => {
    document.querySelector("#how-it-works")?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <div className="min-h-screen overflow-x-hidden bg-canvas text-ink">
      <header className="sticky top-0 z-50 h-16 border-b border-border bg-canvas">
        <nav className="mx-auto flex h-full items-center justify-between px-6 md:px-12" aria-label="Main navigation">
          <Link to="/" className="font-serif text-[22px] font-medium">Buddy</Link>
          <div className="flex items-center gap-4">
            <Button asChild variant="ghost" className="h-auto rounded-[4px] px-2 py-2 text-sm font-normal text-ink-2 shadow-none hover:bg-transparent hover:text-ink">
              <Link to="/login">Sign in</Link>
            </Button>
            <Button asChild className="h-auto rounded-[3px] bg-accent px-4 py-[7px] text-[13px] font-medium text-surface shadow-none hover:bg-accent">
              <Link to="/signup">Get started</Link>
            </Button>
          </div>
        </nav>
      </header>

      <main>
        <section className="relative flex min-h-[calc(100vh-64px)] items-center justify-center overflow-hidden px-6 py-20 text-center">
          <HeroBackground />
          <div className="relative z-10 flex w-full flex-col items-center">
            <p className="mb-12 inline-block rounded-[4px] border border-border px-[14px] py-1.5 font-mono text-[11px] text-ink-3">Built at HackRice 16 · Sep 2026</p>
            <h1 className="max-w-[700px] font-serif text-[40px] leading-[1.08] sm:text-[52px] lg:text-[64px] xl:text-[88px]">
              <span className="block font-normal italic">Your attention</span>
              <span className="block font-semibold not-italic">has a story.</span>
            </h1>
            <p className="mt-7 max-w-[460px] text-lg leading-[1.65] text-ink-2">Buddy watches how you work, understands when you drift, and coaches you back — quietly, through your wrist.</p>
            <div className="mt-11 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Button asChild className="h-auto rounded-[3px] bg-accent px-6 py-2.5 text-sm font-medium text-surface shadow-none hover:bg-accent">
                <Link to="/signup">Get started →</Link>
              </Button>
              <Button type="button" variant="outline" onClick={scrollToHowItWorks} className="h-auto rounded-[3px] border-border bg-transparent px-6 py-2.5 text-sm font-normal text-ink-2 shadow-none hover:bg-transparent hover:text-ink">
                See how it works
              </Button>
            </div>
            <div className="mt-[72px] w-full overflow-x-auto pb-2">
              <div className="mx-auto inline-flex min-w-max border-y border-border bg-transparent text-left">
                {[["84", "Live score", "text-ink"], ["4h 22m", "Focus today", "text-ink"], ["1", "Incident", "text-incident"]].map(([value, label, color], index) => (
                  <div key={label} className={`px-9 py-5 ${index ? "border-l border-border-2" : ""}`}>
                    <p className={`font-mono text-[28px] font-medium ${color}`}>{value}</p>
                    <p className="mt-1 text-xs text-ink-3">{label}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="bg-canvas px-6 py-20 md:px-12">
          <div className="mx-auto max-w-[900px]">
            <SectionLabel>Why Buddy exists</SectionLabel>
            <div className="mt-8 font-serif text-[32px] leading-[1.25] sm:text-[40px] lg:text-[48px]">
              <p>You sit down to study.</p>
              <p className="italic text-ink-3">Two hours later, you've done everything except the thing that mattered.</p>
            </div>
            <p className="mt-11 font-sans text-lg font-normal text-accent">Buddy fixes that.</p>
            <aside className="mt-12 max-w-[520px] border-l-2 border-border pl-3.5 text-[13px] leading-[1.6] text-[#868B86]">
              Your computer usage is tracked against our in-house trained machine learning model, processed through multiple layers of filtration — giving you a clear picture of your productivity in the palm of your hand.
            </aside>
            <div className="mt-20 border-t border-border" />
          </div>
        </section>

        <section id="how-it-works" className="scroll-mt-16 bg-canvas px-6 py-[60px] md:px-12">
          <div className="mx-auto max-w-[900px]">
            <div className="mb-14"><SectionLabel>How it works</SectionLabel></div>
            {processRows.map((row) => (
              <div key={row.number} className="group grid grid-cols-[48px_1fr] gap-7 border-t border-border py-6 md:grid-cols-[48px_1fr_auto]">
                <span className="font-mono text-xs text-ink-3">{row.number}</span>
                <div>
                  <h2 className="font-sans text-[18px] font-medium text-[#1F2933] transition-colors duration-[120ms] ease-linear group-hover:text-[#3F6B5B]">{row.title}</h2>
                  <p className="mt-2.5 max-w-[520px] text-sm leading-[1.65] text-ink-2">{row.description}</p>
                </div>
                <span className="hidden whitespace-nowrap font-mono text-[11px] text-ink-3 md:block">{row.tag}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="bg-surface px-6 py-20 md:px-12">
          <div className="mx-auto max-w-[900px]">
            <SectionLabel>What Buddy sees</SectionLabel>
            <h2 className="mt-4 mb-16 font-serif text-[32px] font-normal leading-tight sm:text-[40px] lg:text-[48px]">Every signal that matters.</h2>
            <div className="grid gap-x-10 gap-y-8 sm:grid-cols-2">
              {signals.map(([title, description]) => (
                <article key={title}>
                  <div className="mb-3.5 h-0.5 w-5 bg-accent" />
                  <h3 className="mb-2.5 text-[15px] font-medium">{title}</h3>
                  <p className="text-[13px] leading-[1.65] text-ink-2">{description}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section
          className="buddy-wearable-section border-t border-border px-6 py-20 md:px-12"
          style={{
            backgroundImage: `url(${wearableAsset.url})`,
            backgroundSize: "cover",
            backgroundPosition: "center",
          }}
        >
          <div className="mx-auto max-w-[900px]">
            <p className="mb-12 font-mono text-[11px] tracking-[0.08em] text-ink-3">The wearable</p>
            <div className="grid gap-12 lg:grid-cols-2 lg:gap-20">
              <div>
                <h2 className="font-serif text-[56px] font-normal leading-[1.1] text-ink">Buddy Wearable</h2>
                <p className="mt-4 mb-12 font-sans text-[17px] leading-[1.6] text-ink-2">
                  A small device. A calm voice.<br />Your focus, back on track.
                </p>
                <div>
                  {[
                    ["Listens to your goals", "Speak what you want to achieve before you start. Buddy remembers all session."],
                    ["Tracks your focus silently", "Watches your computer usage continuously. Scores your activity against your goals."],
                    ["Speaks when you drift", "When your productivity drops and holds low, a calm voice through the speaker brings you back — no phone, no popup."],
                  ].map(([name, detail]) => (
                    <div key={name} className="border-t border-border py-4">
                      <p className="font-sans text-sm font-medium text-ink">{name}</p>
                      <p className="mt-1 font-sans text-[13px] leading-[1.5] text-ink-2">{detail}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <p className="mb-8 font-mono text-[11px] tracking-[0.08em] text-ink-3">What it sounds like</p>
                <div className="font-serif text-[34px] leading-[1.2]">
                  <p className="mb-1 text-ink">You don't check your phone.</p>
                  <p className="mb-8 italic text-ink-3">You don't read a notification.</p>
                </div>
                <blockquote className="max-w-[360px] border-l-2 border-accent py-4 pl-5 pr-5 font-mono text-sm leading-[1.65] text-ink">
                  You've been away for 4 minutes.<br />Want to come back?
                </blockquote>
                <p className="mb-8 ml-[22px] mt-0 font-mono text-[11px] text-ink-3">— Buddy, 9:14 PM</p>
                <p className="font-serif text-[34px] font-semibold leading-[1.2] text-accent">And you come back.</p>
              </div>
            </div>
          </div>
          <p className="buddy-wearable-caption absolute bottom-7 right-6 z-10 md:right-12">
            Buddy Wearable · HackRice 16 prototype
          </p>
        </section>

        <section className="border-t border-border bg-canvas px-6 py-20 md:px-12">
          <div className="mx-auto max-w-[900px]">
            <div className="mb-14"><SectionLabel>Your journey</SectionLabel></div>
            <div className="grid grid-cols-2 md:grid-cols-5">
              {steps.map(([step, label, detail]) => (
                <div key={step} className="border-t border-border px-4 py-5 md:px-6">
                  <p className="mb-2 font-mono text-[10px] text-ink-3">{step}</p>
                  <h3 className="mb-1.5 text-sm font-medium leading-snug">{label}</h3>
                  <p className="text-xs leading-relaxed text-ink-3">{detail}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="w-full border-t border-border bg-canvas px-12 py-12 text-center">
          <span className="mb-9 block text-center font-mono text-[11px] tracking-[0.08em] text-[#868B86]">
            Built at HackRice 16 · September 2026
          </span>
          <div className="mx-auto flex max-w-[900px] flex-wrap items-center justify-center gap-y-8 gap-x-8 md:flex-nowrap md:gap-12">
            {[
              { src: "/logos/gemini.png", alt: "Gemini", filter: "none" as const, size: "h-6 md:h-8" as const },
              { src: "/logos/elevenlabs.png", alt: "ElevenLabs", filter: "none" as const, size: "h-6 md:h-8" as const },
              { src: "/logos/matlab.png", alt: "MATLAB", filter: "none" as const, size: "h-8 md:h-10" as const },
              { src: "/logos/tigerdata.png", alt: "Tiger Data", filter: "none" as const, size: "h-6 md:h-8" as const },
              { src: "/logos/lovable.svg", alt: "Lovable", filter: "brightness(0) saturate(100%)" as const, size: "h-6 md:h-8" as const },
              { src: "/logos/notability.png", alt: "Notability", filter: "none" as const, size: "h-6 md:h-8" as const },
            ].map((logo) => (
              <img
                key={logo.alt}
                src={logo.src}
                alt={logo.alt}
                className={`block w-auto max-w-[120px] object-contain opacity-100 ${logo.size}`}
                style={{ filter: logo.filter }}
              />
            ))}
          </div>
        </section>

        <section className="bg-canvas px-6 py-[100px] text-center md:px-12">
          <h2 className="mx-auto max-w-[600px] font-serif text-[36px] font-normal italic leading-[1.2] sm:text-[48px] lg:text-[58px]">Ready to understand your focus?</h2>
          <p className="mt-4 mb-11 text-[15px] text-ink-2">Built for students who want to understand how their attention actually works.</p>
          <Button asChild className="inline-flex h-auto rounded-[3px] bg-accent px-8 py-3 text-sm font-medium text-surface shadow-none hover:bg-accent">
            <Link to="/signup">Create your Buddy account</Link>
          </Button>
          <p className="mt-3.5 text-[13px] text-ink-3">Free during HackRice 16.</p>
        </section>
      </main>

      <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border bg-canvas px-6 py-7 md:px-12">
        <p className="font-serif text-base text-ink-2">Buddy</p>
        <p className="font-mono text-xs text-ink-3">HackRice 16 · 2026</p>
      </footer>
    </div>
  );
}
