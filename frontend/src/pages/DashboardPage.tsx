import { Link } from "@tanstack/react-router";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import { Eyebrow } from "@/components/dashboard/DashboardShared";
import { WaitingState } from "@/components/dashboard/WaitingState";
import { Button } from "@/components/ui/button";
import { useDashboardData } from "@/hooks/useDashboardData";
import { useUserProfile } from "@/hooks/useUserProfile";
import { getTriggerState, toDisplay } from "@/lib/format";
import { taskService } from "@/services/taskService";

function greetingForHour(hour: number) {
  if (hour >= 5 && hour < 12) return "Good morning";
  if (hour >= 12 && hour < 18) return "Good afternoon";
  return "Good evening";
}

export default function DashboardPage() {
  const { profile } = useUserProfile();
  const {
    currentScore,
    tasks,
    currentTask,
    tomorrowTasks,
    setTomorrowTasks,
    wearable,
    suggestions,
    incidentCounts,

  } = useDashboardData();

  const [hour, setHour] = useState(12);
  const [doneIds, setDoneIds] = useState<string[]>([]);
  const [newTomorrowTask, setNewTomorrowTask] = useState("");
  const [addingTomorrow, setAddingTomorrow] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => setHour(new Date().getHours()), []);
  useEffect(() => { if (addingTomorrow) inputRef.current?.focus(); }, [addingTomorrow]);

  const addTask = () => {
    const title = newTomorrowTask.trim();
    if (!title) return;
    void taskService.addTomorrow(title, "medium").then((created) => {
      setTomorrowTasks((current) => [...(current ?? []), { id: created.id, title: created.title, priority: "medium" }]);
    });
    setNewTomorrowTask("");
    setAddingTomorrow(false);
  };

  const onTaskKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") addTask();
    if (event.key === "Escape") { setAddingTomorrow(false); setNewTomorrowTask(""); }
  };

  const scoreState = getTriggerState(currentScore?.score, currentScore?.trigger);
  const displayScore = toDisplay(currentScore?.score);
  const upcoming = (tasks ?? []).filter((task) => task.id !== currentTask?.id).slice(0, 2);
  const tomorrow = tomorrowTasks ?? [];

  return (
    <main className="min-h-[calc(100vh-56px)] bg-canvas px-5 py-8 pb-20 sm:px-8 lg:px-10">
      <div className="mx-auto max-w-[1280px]">
        <h1 className="mb-8 font-serif text-[32px] font-normal">{greetingForHour(hour)}, {profile.name}.</h1>
        <div className="grid gap-6 lg:grid-cols-2">
          <section className="rounded-[4px] border border-border bg-surface p-7">
            <Eyebrow className="mb-2">current task</Eyebrow>
            {currentTask?.title ? (
              <>
                <h2 className="mb-1 text-[18px] font-medium">{currentTask.title}</h2>
                <p className="mb-5 text-[13px] text-ink-2">
                  in {currentScore?.app_name || "—"}
                  {currentScore?.session_duration != null ? ` · ${currentScore.session_duration} min` : ""}
                </p>
              </>
            ) : (
              <div className="mb-5">
                <p className="font-mono text-[28px] leading-none text-border">—</p>
                <p className="mt-1 text-[13px] text-ink-3">Waiting for your goals.</p>
              </div>
            )}
            <div className="border-t border-border-2 pt-5">
              <Eyebrow className="mb-2">productivity</Eyebrow>
              {!currentScore ? (
                <div className="mb-4">
                  <p className="font-mono text-[64px] leading-none text-border sm:text-[96px]">—</p>
                  <p className="mt-2 text-[13px] text-ink-3">waiting for data</p>
                </div>
              ) : (
                <div className="mb-4 flex items-baseline gap-3 transition-colors duration-200" style={{ color: scoreState.color }}>
                  <span className="font-mono text-[64px] leading-none">{displayScore}</span>
                  <span className="font-mono text-[14px]">{scoreState.label}</span>
                </div>
              )}
              <div className="mb-5 flex gap-4">
                <p className={`font-mono text-[11px] ${currentScore ? "text-drift" : "text-border"}`}>{incidentCounts.soft} <span className={`font-sans ${currentScore ? "text-ink-3" : "text-border"}`}>soft triggers today</span></p>
                <p className={`font-mono text-[11px] ${currentScore ? "text-incident" : "text-border"}`}>{incidentCounts.hard} <span className={`font-sans ${currentScore ? "text-ink-3" : "text-border"}`}>hard triggers today</span></p>
              </div>
            </div>
            <div className="border-t border-border-2 pt-5">
              <div className="flex items-center gap-2"><span className={`buddy-pulse size-1.5 rounded-full ${wearable?.connected ? "bg-accent" : "bg-ink-3"}`} /><span className="font-mono text-[11px] text-accent">{wearable?.connected ? "wearable connected" : "wearable offline"}</span></div>
              {wearable?.last_trigger_time ? <p className="mt-1 font-mono text-[11px] text-ink-3">last check-in {wearable.last_trigger_time}</p> : null}
            </div>
            <Button asChild className="mt-6 h-auto w-full rounded-[3px] bg-ink px-4 py-[11px] text-[14px] text-canvas shadow-none hover:bg-plot-grid"><Link to="/live">Analyse now →</Link></Button>
          </section>

          <section className="rounded-[4px] border border-border bg-surface p-7">
            {currentTask?.title ? (
              <>
                <Eyebrow className="mb-3">next priority</Eyebrow>
                <div className="mb-5 border-l-[3px] border-accent pl-4"><h2 className="mb-1.5 font-serif text-[28px] font-normal leading-[1.2]">{currentTask.title}</h2><p className="font-mono text-[12px] text-incident">Due in {currentTask.minutes_left} minutes</p></div>
              </>
            ) : (
              <div className="buddy-waiting-in">
                <Eyebrow className="mb-5">next priority</Eyebrow>
                <p className="mb-3 font-serif text-[28px] font-normal italic leading-[1.2] text-ink-3">Nothing queued yet.</p>
                <p className="mb-6 text-[14px] text-ink-2">Tell me what you want to work on.</p>
                {/* Phase 2: triggers wearable voice input */}
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setAddingTomorrow(true)}
                  className="mb-5 h-auto rounded-[3px] border-border bg-transparent px-4 py-2 text-[13px] font-normal text-accent shadow-none hover:bg-canvas"
                >
                  + Speak a task
                </Button>
              </div>
            )}
            <div className="border-t border-border-2 pt-5">
              <Eyebrow className="mb-3">up next</Eyebrow>
              {upcoming.length === 0 ? (
                <WaitingState variant="text" message="Nothing else scheduled." />
              ) : (
                upcoming.map((task) => <div key={task.id} className="grid grid-cols-[1fr_auto] items-center border-b border-border-2 py-2.5"><p className={`text-[14px] ${task.status === "missed" ? "text-ink-3 line-through" : "text-ink"}`}>{task.title}</p><p className={`font-mono text-[11px] ${task.status === "missed" ? "text-incident" : "text-ink-3"}`}>{task.due} · {task.status.replace("_", " ")}</p></div>)
              )}
            </div>
            {suggestions && suggestions.length > 0 ? (
              <div className="mt-5 border-t border-border-2 pt-5"><Eyebrow className="mb-3">from your wearable</Eyebrow>{suggestions.map((suggestion) => <p key={suggestion.id} className="border-b border-border-2 py-2 text-[13px] text-ink-2"><span className="font-mono text-drift">✦</span> {suggestion.text}</p>)}</div>
            ) : null}
          </section>
        </div>

        <section className="mt-8 border-t border-border pt-7">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-mono text-[11px] text-ink-3">what you told Buddy</p>
              <p className="mt-1 text-[12px] text-ink-3">Spoken through your wearable</p>
            </div>
            <Button type="button" variant="ghost" onClick={() => setAddingTomorrow(true)} className="h-auto rounded-[3px] px-1 py-1 text-[13px] font-normal text-accent shadow-none hover:bg-transparent hover:text-ink">+ Add task</Button>
          </div>
          <div className="mt-3">
            {tomorrow.length === 0 && !addingTomorrow ? (
              <div className="buddy-waiting-in py-2">
                <p className="mb-1 text-[15px] text-ink-3">Nothing yet.</p>
                <p className="text-[13px] leading-[1.5] text-ink-3">Speak your tasks to Buddy when you're ready to start.</p>
              </div>
            ) : null}
            {tomorrow.map((task) => {
              const done = doneIds.includes(task.id);
              return (
                <div key={task.id} className="flex items-center gap-3 border-b border-border-2 py-2.5">
                  <Button type="button" variant="ghost" aria-label={`Mark ${task.title} ${done ? "not done" : "done"}`} onClick={() => { void taskService.updateStatus(task.id, done ? "todo" : "done"); setDoneIds((ids) => done ? ids.filter((id) => id !== task.id) : [...ids, task.id]); }} className="size-5 shrink-0 rounded-full border border-border p-0 shadow-none hover:bg-accent-2"><span className="text-[10px] text-accent">{done ? "✓" : ""}</span></Button>
                  <span className={`text-[14px] ${done ? "text-ink-3 line-through" : "text-ink"}`}>{task.title}</span>
                  <span className={`font-mono text-[10px] ${task.priority === "high" ? "text-incident" : "text-drift"}`}>{task.priority}</span>
                </div>
              );
            })}
            {addingTomorrow ? <input ref={inputRef} value={newTomorrowTask} onChange={(event) => setNewTomorrowTask(event.target.value)} onKeyDown={onTaskKeyDown} placeholder="What's on for tomorrow?" className="mt-2 w-full border-0 border-b border-border bg-transparent px-0 py-2 text-[14px] outline-none placeholder:text-ink-3 focus:border-accent" /> : null}
          </div>
        </section>

        <section className="mt-10 flex flex-col gap-4 border-t border-border pt-7 sm:flex-row sm:items-center sm:justify-between"><p className="font-serif text-[22px] italic">See how your day went</p><Link to="/discover" className="text-[14px] font-medium text-accent hover:text-ink">Go to Discover →</Link></section>
      </div>
    </main>
  );
}
