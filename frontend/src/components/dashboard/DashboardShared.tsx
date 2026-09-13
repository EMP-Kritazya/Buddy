import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { WaitingState } from "@/components/dashboard/WaitingState";
import { triggerColor, type TriggerLevel } from "@/lib/format";
import type { CommentaryItem } from "@/types";

export function scoreTone(score: number) {
  if (score > 70) return "var(--color-accent)";
  if (score >= 50) return "var(--color-drift)";
  return "var(--color-incident)";
}

export function scoreStatus(score: number) {
  if (score > 70) return "focused";
  if (score >= 50) return "drifting";
  return "distracted";
}

export function Eyebrow({ children, className = "" }: { children: string; className?: string }) {
  return <p className={`font-mono text-[10px] text-ink-3 ${className}`}>{children}</p>;
}

/** Chart-ready point: score already converted to 0–100. */
export interface ChartPoint {
  time: string;
  score: number;
  trigger: TriggerLevel;
}

type TooltipPayload = { payload?: ChartPoint };

function ChartTooltip({ active, payload }: { active?: boolean; payload?: TooltipPayload[] }) {
  const point = payload?.[0]?.payload;
  if (!active || !point) return null;
  return <div className="rounded-[3px] bg-plot-grid px-3 py-2 font-mono text-[12px] text-canvas">{point.time} · {point.score}</div>;
}

const axisProps = {
  axisLine: false,
  tickLine: false,
  stroke: "var(--plot-axis)",
  tick: { fontFamily: "var(--font-mono)", fontSize: 10 },
} as const;

export interface FocusChartProps {
  data: ChartPoint[] | null;
  fullDay?: boolean;
  /** Stroke colour derived from the latest trigger level. */
  stroke?: string;
  stats?: { current: string | number; peak: string | number; low: string | number };
  waiting?: { message: string; submessage?: string };
}

export function FocusChart({ data, fullDay = false, stroke, stats, waiting }: FocusChartProps) {
  const height = fullDay ? "min-h-[200px] h-[228px] sm:h-[288px]" : "min-h-[200px] h-[208px] sm:h-[268px]";
  const line = stroke ?? triggerColor(data?.[data.length - 1]?.trigger ?? 0);
  const incidents = (data ?? []).filter((point) => point.trigger === 2);
  const empty = !data || data.length === 0;

  return (
    <div className="overflow-hidden rounded-[4px] bg-plot-bg">
      <div className={`${height} ${empty ? "flex items-center justify-center" : "p-4 sm:p-6"}`}>
        {empty ? (
          <WaitingState
            tone="light"
            message={waiting?.message ?? "Waiting for score data"}
            submessage={waiting?.submessage}
          />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            {fullDay ? (
              <AreaChart data={data} margin={{ top: 4, right: 4, left: -8, bottom: 0 }}>
                <defs><linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={line} stopOpacity={0.3} /><stop offset="95%" stopColor={line} stopOpacity={0} /></linearGradient></defs>
                <CartesianGrid strokeDasharray="1 4" stroke="var(--plot-grid)" vertical={false} />
                <XAxis dataKey="time" {...axisProps} />
                <YAxis domain={[0, 100]} width={28} {...axisProps} />
                <Tooltip content={<ChartTooltip />} cursor={{ stroke: "var(--plot-axis)" }} />
                <Area type="monotone" dataKey="score" stroke={line} strokeWidth={1.5} fill="url(#areaGradient)" />
                {incidents.map((point) => <ReferenceDot key={point.time} x={point.time} y={point.score} r={5} fill="var(--color-incident)" stroke="var(--plot-bg)" strokeWidth={2} />)}
              </AreaChart>
            ) : (
              <LineChart data={data} margin={{ top: 4, right: 4, left: -8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="1 4" stroke="var(--plot-grid)" vertical={false} />
                <XAxis dataKey="time" {...axisProps} />
                <YAxis domain={[0, 100]} width={28} {...axisProps} />
                <Tooltip content={<ChartTooltip />} cursor={{ stroke: "var(--plot-axis)" }} />
                <Line type="monotone" dataKey="score" stroke={line} strokeWidth={2} dot={false} activeDot={{ r: 4, fill: line, stroke: "var(--plot-bg)" }} />
                {incidents.map((point) => <ReferenceDot key={point.time} x={point.time} y={point.score} r={5} fill="var(--color-incident)" stroke="var(--plot-bg)" strokeWidth={2} />)}
              </LineChart>
            )}
          </ResponsiveContainer>
        )}
      </div>
      {stats ? (
        <div className="grid grid-cols-3 border-t border-plot-grid bg-plot-footer px-6 py-3 text-center">
          {[[stats.current, "Current"], [stats.peak, "Peak"], [stats.low, "Low"]].map(([value, label]) => <div key={label} className="border-l border-plot-grid first:border-l-0"><p className={`font-mono text-[20px] ${value === "—" ? "text-border" : "text-canvas"}`}>{value}</p><p className="text-[10px] text-ink-3">{label}</p></div>)}
        </div>
      ) : null}
    </div>
  );
}

const commentaryTone = {
  positive: "border-accent text-ink",
  warning: "border-drift text-drift",
  incident: "border-incident text-incident",
};

export function CommentaryPanel({ title, subtitle, items, live = false, waiting }: { title: string; subtitle: string; items: CommentaryItem[] | null; live?: boolean; waiting?: { message: string; submessage?: string } }) {
  return (
    <aside className="rounded-[4px] border border-border bg-surface p-6 lg:sticky lg:top-[88px] lg:max-h-[calc(100vh-120px)] lg:overflow-y-auto">
      <h2 className="text-[14px] font-medium">{title}</h2>
      <p className="mb-5 mt-1 font-mono text-[10px] text-ink-3">{subtitle}</p>
      <div className="border-t border-border-2 pt-4">
        {!items || items.length === 0 ? (
          <WaitingState
            variant="reflective"
            message={waiting?.message ?? "Buddy is watching."}
            submessage={waiting?.submessage}
          />
        ) : (
          items.map((item, index) => (
            <article key={item.id} className={`${index === 0 && live ? "buddy-commentary-in" : ""} border-b border-l-[3px] border-b-border-2 py-3 pl-4 ${commentaryTone[item.type]}`}>
              <p className="mb-1.5 font-mono text-[11px] text-ink-3">{item.period ?? item.time}</p>
              <p className="text-[14px] leading-[1.5]">{item.text}</p>
            </article>
          ))
        )}
      </div>
    </aside>
  );
}
