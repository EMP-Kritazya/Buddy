import { Link } from "@tanstack/react-router";

import { CommentaryPanel, Eyebrow, FocusChart, type ChartPoint } from "@/components/dashboard/DashboardShared";
import { WaitingState } from "@/components/dashboard/WaitingState";
import { Button } from "@/components/ui/button";
import { useDiscoverData } from "@/hooks/useDiscoverData";
import { formatMins, formatTime, toDisplay } from "@/lib/format";

export default function DiscoverPage() {
  const { todayScores, summary, incidents, dayCommentary } = useDiscoverData();

  const points: ChartPoint[] = (todayScores ?? []).map((sample) => ({
    time: formatTime(sample.timestamp),
    score: toDisplay(sample.score) ?? 0,
    trigger: sample.trigger,
  }));

  const stats: Array<[string | number, string]> = [
    [summary ? formatMins(summary.focus_time_mins) : "—", "Focus time"],
    [summary ? toDisplay(summary.avg_score) ?? "—" : "—", "Avg score"],
    [incidents?.length ?? "—", "Incidents"],
    [summary ? `${summary.tasks_completed}/${summary.tasks_total}` : "—", "Tasks done"],
  ];

  return (
    <main className="min-h-[calc(100vh-56px)] bg-canvas px-5 py-8 pb-20 sm:px-8 lg:px-10">
      <div className="mx-auto max-w-[1280px]">
        <header className="mb-2 flex items-baseline justify-between gap-4"><h1 className="font-serif text-[36px] font-normal">Discover</h1><p className="font-mono text-[12px] text-ink-3">12 Sep 2026</p></header>
        <p className="mb-8 text-[16px] text-ink-2">Here's how your attention moved today.</p>
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_300px] xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="min-w-0">
            <section className="mb-7 grid grid-cols-2 rounded-[4px] border border-border bg-surface sm:grid-cols-4">{stats.map(([value, label], index) => <div key={label} className={`px-4 py-5 sm:px-6 ${index % 2 ? "border-l border-border-2" : ""} ${index > 1 ? "border-t border-border-2 sm:border-t-0" : ""} ${index === 2 ? "sm:border-l" : ""}`}><p className={`font-mono text-[28px] ${value === "—" ? "text-border" : ""}`}>{value}</p><p className="text-[11px] text-ink-3">{label}</p></div>)}</section>
            <section>
              <Eyebrow className="mb-3">your full day · 8:00 AM – 9:35 PM</Eyebrow>
              <FocusChart data={points} fullDay waiting={{ message: "No data yet today", submessage: "Data appears as you work" }} />
              {summary?.strongest_period ? <p className="my-3 text-[13px] text-ink-2">Strongest period: {summary.strongest_period}</p> : null}
            </section>
            <section className="mt-7">
              <Eyebrow className="mb-4">what interrupted you</Eyebrow>
              {!incidents || incidents.length === 0 ? (
                <WaitingState variant="text" message="Nothing interrupted you today." />
              ) : (
                incidents.map((incident) => <article key={incident.id} className="grid gap-2 border-b border-border-2 py-4 sm:grid-cols-[64px_1fr_auto]"><time className="font-mono text-[11px] text-ink-3">{formatTime(incident.timestamp)}</time><div><p className="text-[14px] font-medium">{incident.app_name}</p><p className="text-[13px] text-ink-2">{incident.duration_secs} seconds · Score dropped to {toDisplay(incident.score)}</p></div>{incident.intervened ? <p className="font-mono text-[10px] text-accent">Buddy intervened ✓</p> : null}</article>)
              )}
            </section>
            {summary?.tomorrow_suggestion ? (
              <section className="mt-7 border-t border-border pt-6"><Eyebrow className="mb-2">tomorrow →</Eyebrow><blockquote className="max-w-[560px] border-l-2 border-highlight pl-4 font-serif text-[24px] italic leading-[1.35]">{summary.tomorrow_suggestion}</blockquote></section>
            ) : null}
            <div className="mt-7 flex flex-wrap gap-3"><Button type="button" variant="outline" onClick={() => { /* Phase 2: open Notability export */ }} className="h-auto rounded-[3px] border-border bg-transparent px-[18px] py-[9px] text-[13px] text-ink shadow-none hover:bg-surface">Open in Notability →</Button><Button asChild className="h-auto rounded-[3px] bg-accent px-[18px] py-[9px] text-[13px] text-surface shadow-none hover:bg-accent hover:brightness-90"><Link to="/journal">Open Journal →</Link></Button></div>
          </div>
          <CommentaryPanel
            title="Buddy's day analysis"
            subtitle="Gemini · end of day reflection"
            items={dayCommentary}
            waiting={{ message: "Analysis builds throughout the day as data comes in." }}
          />
        </div>
      </div>
    </main>
  );
}
