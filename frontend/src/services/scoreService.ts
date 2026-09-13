import { apiClient } from "@/lib/apiClient";
import { triggerFromScore } from "@/lib/format";
import { toScoreSample } from "@/lib/previewAdapters";
import { previewData } from "@/data/previewData";
import type { CurrentScore, ScoreSample } from "@/types/api";

export const scoreService = {
  getCurrent: async (): Promise<CurrentScore | null> => {
    // Phase 2: GET /api/scores/current (polled every 30s)
    const real = await apiClient.get<CurrentScore>("/api/scores/current");
    if (real) return real;

    const user = previewData.user;
    return {
      score: user.score / 100,
      app_name: user.currentApp,
      window_title: user.currentWindow,
      session_duration: user.sessionDuration,
      trigger: triggerFromScore(user.score),
    };
  },

  getLive: async (): Promise<ScoreSample[] | null> => {
    // Phase 2: GET /api/scores/live (polled every 30s)
    const real = await apiClient.get<ScoreSample[]>("/api/scores/live");
    if (real) return real;
    return previewData.liveScores.map(toScoreSample);
  },

  getToday: async (): Promise<ScoreSample[] | null> => {
    // Phase 2: GET /api/scores/today (refreshed every 5 min)
    const real = await apiClient.get<ScoreSample[]>("/api/scores/today");
    if (real) return real;
    return previewData.todayScores.map(toScoreSample);
  },
};
