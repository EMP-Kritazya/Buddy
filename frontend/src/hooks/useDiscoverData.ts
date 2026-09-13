import { useEffect, useState } from "react";

import { geminiService } from "@/services/geminiService";
import { incidentService } from "@/services/incidentService";
import { scoreService } from "@/services/scoreService";
import { summaryService } from "@/services/summaryService";
import type { CommentaryItem } from "@/types";
import type { ApiDailySummary, ApiIncident, ScoreSample } from "@/types/api";

/** Discover page data — refreshed every 5 minutes. */
export const useDiscoverData = () => {
  const [todayScores, setTodayScores] = useState<ScoreSample[] | null>(null);
  const [summary, setSummary] = useState<ApiDailySummary | null>(null);
  const [incidents, setIncidents] = useState<ApiIncident[] | null>(null);
  const [dayCommentary, setDayCommentary] = useState<CommentaryItem[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAll = async () => {
      // Phase 2: /api/scores/today, /api/summary/today, /api/incidents/today, /api/gemini/day-analysis
      const [scores, sum, inc, comments] = await Promise.all([
        scoreService.getToday(),
        summaryService.getToday(),
        incidentService.getToday(),
        geminiService.getDayAnalysis(),
      ]);

      setTodayScores(scores);
      setSummary(sum);
      setIncidents(inc);
      setDayCommentary(comments);
      setLoading(false);
    };

    void fetchAll();
    const interval = window.setInterval(() => void fetchAll(), 300000);
    return () => window.clearInterval(interval);
  }, []);

  return { todayScores, summary, incidents, dayCommentary, loading };
};
