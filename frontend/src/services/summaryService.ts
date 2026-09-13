import { apiClient } from "@/lib/apiClient";
import { previewData } from "@/data/previewData";
import type { ApiDailySummary } from "@/types/api";

export const summaryService = {
  getToday: async (): Promise<ApiDailySummary | null> => {
    // Phase 2: GET /api/summary/today (refreshed every 5 min)
    const real = await apiClient.get<ApiDailySummary>("/api/summary/today");
    if (real) return real;

    const summary = previewData.summary;
    return {
      focus_time_mins: 262,
      avg_score: summary.avgScore / 100,
      incidents: summary.incidents,
      tasks_completed: summary.tasksCompleted,
      tasks_total: summary.tasksTotal,
      strongest_period: summary.strongestPeriod,
      gemini_reflection: summary.geminiReflection,
      tomorrow_suggestion: summary.tomorrowSuggestion,
    };
  },
};
