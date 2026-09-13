import type { ScoreBand, ScorePoint } from "@/types";

export function scoreBand(score: number): ScoreBand {
  if (score > 70) return "productive";
  if (score >= 40) return "drifting";
  return "incident";
}

export function bandLabel(band: ScoreBand): string {
  if (band === "productive") return "Focused";
  if (band === "drifting") return "Drifting";
  return "Off task";
}

/**
 * Derives band, label and simple trend from a score plus its recent history.
 * Labels are always returned alongside colours so meaning never relies on hue.
 */
export function useProductivityScore(score: number, history: ScorePoint[] = []) {
  const band = scoreBand(score);
  const previous = history.length > 1 ? history[history.length - 2]!.score : score;
  const delta = score - previous;
  const trend: "rising" | "steady" | "falling" =
    delta > 2 ? "rising" : delta < -2 ? "falling" : "steady";

  return { band, label: bandLabel(band), delta, trend };
}
