import { CommentaryPanel, Eyebrow, FocusChart, type ChartPoint } from "@/components/dashboard/DashboardShared";
import { WaitingState } from "@/components/dashboard/WaitingState";
import { useLiveData } from "@/hooks/useLiveData";
import { formatTime, getTriggerState, toDisplay, triggerColor } from "@/lib/format";

export default function LivePage() {
  const { liveScores, currentScore, wearableMessages, commentary } = useLiveData();

  const points: ChartPoint[] = (liveScores ?? []).map((sample) => ({
    time: formatTime(sample.timestamp),
    score: toDisplay(sample.score) ?? 0,
    trigger: sample.trigger,
  }));

  const scoreState = getTriggerState(currentScore?.score, currentScore?.trigger);
  const current = toDisplay(currentScore?.score);
  const stroke = triggerColor(points[points.length - 1]?.trigger ?? 0);
  const scores = points.map((point) => point.score);

  return (
    <main className="min-h-[calc(100vh-56px)] bg-canvas px-5 py-8 pb-20 sm:px-8 lg:px-10">
      <div className="mx-auto max-w-[1280px]">
        <header className="mb-8 flex items-baseline justify-between gap-4"><h1 className="font-serif text-[36px] font-normal">Live</h1><p className="font-mono text-[11px] text-ink-3">Updates every 30 seconds</p></header>
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_300px] xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="min-w-0">
            <section className="mb-7 grid rounded-[4px] border border-border bg-surface sm:grid-cols-3">
              <div className="border-b border-border-2 px-6 py-5 sm:border-b-0 sm:border-r"><p className="font-mono text-[48px] leading-none transition-colors duration-200" style={{ color: currentScore ? scoreState.color : "var(--color-border)" }}>{current ?? "—"}</p><p className="mt-2 font-mono text-[11px] text-ink-3">{currentScore ? `live score · ${scoreState.label}` : "waiting for data"}</p></div>
              <div className="border-b border-border-2 px-6 py-5 sm:border-b-0 sm:border-r"><p className={`text-[16px] font-medium ${currentScore?.app_name ? "" : "text-border"}`}>{currentScore?.app_name || "—"}</p>{currentScore?.window_title ? <p className="text-[12px] text-ink-2">{currentScore.window_title}</p> : null}<p className="mt-2 font-mono text-[11px] text-ink-3">current app</p></div>
              <div className="px-6 py-5"><p className={`font-mono text-[32px] ${currentScore?.session_duration == null ? "text-border" : ""}`}>{currentScore?.session_duration != null ? `${currentScore.session_duration} min` : "—"}</p><p className="mt-2 font-mono text-[11px] text-ink-3">session time</p></div>
            </section>
            <section>
              <Eyebrow className="mb-3">your focus · last 30 minutes</Eyebrow>
              <FocusChart
                data={points}
                stroke={stroke}
                waiting={{ message: "Waiting for score data", submessage: "Make sure the PC agent is running" }}
                stats={{
                  current: current ?? "—",
                  peak: scores.length ? Math.max(...scores) : "—",
                  low: scores.length ? Math.min(...scores) : "—",
                }}
              />
            </section>
            <section className="mt-7">
              <Eyebrow className="mb-4">what buddy said today</Eyebrow>
              {!wearableMessages || wearableMessages.length === 0 ? (
                <WaitingState variant="text" message="Buddy hasn't spoken yet today." />
              ) : (
                wearableMessages.map((message) => <article key={`${message.time}-${message.message}`} className="grid grid-cols-[56px_1fr] gap-4 border-b border-border-2 py-3.5"><time className="font-mono text-[11px] text-ink-3">{message.time}</time><div><p className="text-[14px]">{message.message}</p><p className={`mt-1 flex items-center gap-1.5 font-mono text-[10px] ${message.type === "hard" ? "text-incident" : "text-drift"}`}><span className={`size-[5px] rounded-full ${message.type === "hard" ? "bg-incident" : "bg-drift"}`} />{message.type === "hard" ? "Coaching trigger" : "Check-in"}</p></div></article>)
              )}
            </section>
          </div>
          <CommentaryPanel
            title="Buddy's commentary"
            subtitle="Gemini · live analysis"
            items={commentary}
            live
            waiting={{ message: "Buddy is watching.", submessage: "Commentary appears as your session develops." }}
          />
        </div>
      </div>
    </main>
  );
}
