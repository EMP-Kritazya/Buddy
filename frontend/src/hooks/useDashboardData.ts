import { useCallback, useEffect, useState } from "react";

import { geminiService } from "@/services/geminiService";
import { incidentService } from "@/services/incidentService";
import { scoreService } from "@/services/scoreService";
import { taskService } from "@/services/taskService";
import { wearableService } from "@/services/wearableService";
import type { GeminiSuggestion, SpokenTask, TomorrowTask } from "@/types";
import type { ApiCurrentTask, CurrentScore, WearableStatus } from "@/types/api";

/** Master hook for the home dashboard. Every section polls at its own cadence. */
export const useDashboardData = () => {
  const [currentScore, setCurrentScore] = useState<CurrentScore | null>(null);
  const [tasks, setTasks] = useState<SpokenTask[] | null>(null);
  const [currentTask, setCurrentTask] = useState<ApiCurrentTask | null>(null);
  const [tomorrowTasks, setTomorrowTasks] = useState<TomorrowTask[] | null>(null);
  const [wearable, setWearable] = useState<WearableStatus | null>(null);
  const [suggestions, setSuggestions] = useState<GeminiSuggestion[] | null>(null);
  const [incidentCounts, setIncidentCounts] = useState({ soft: 0, hard: 0 });
  const [loading, setLoading] = useState({ score: true, tasks: true, wearable: true, suggestions: true });

  const fetchScore = useCallback(async () => {
    const data = await scoreService.getCurrent();
    setCurrentScore(data);
    setLoading((state) => ({ ...state, score: false }));
  }, []);

  const fetchTasks = useCallback(async () => {
    const [today, current, tomorrow] = await Promise.all([
      taskService.getToday(),
      taskService.getCurrent(),
      taskService.getTomorrow(),
    ]);
    setTasks(today);
    setCurrentTask(current);
    setTomorrowTasks(tomorrow);
    setLoading((state) => ({ ...state, tasks: false }));
  }, []);

  const fetchWearable = useCallback(async () => {
    const data = await wearableService.getStatus();
    setWearable(data);
    setLoading((state) => ({ ...state, wearable: false }));
  }, []);

  const fetchSuggestions = useCallback(async () => {
    const data = await geminiService.getSuggestions();
    setSuggestions(data);
    setLoading((state) => ({ ...state, suggestions: false }));
  }, []);

  const fetchIncidents = useCallback(async () => {
    const data = await incidentService.getToday();
    if (data) {
      setIncidentCounts({
        soft: data.filter((incident) => incident.trigger === 1).length,
        hard: data.filter((incident) => incident.trigger === 2).length,
      });
    }
  }, []);

  useEffect(() => {
    void fetchScore();
    void fetchTasks();
    void fetchWearable();
    void fetchSuggestions();
    void fetchIncidents();

    const scoreInterval = window.setInterval(() => void fetchScore(), 30000);
    const taskInterval = window.setInterval(() => void fetchTasks(), 60000);
    const wearableInterval = window.setInterval(() => void fetchWearable(), 10000);
    const suggestionInterval = window.setInterval(() => {
      void fetchSuggestions();
      void fetchIncidents();
    }, 300000);

    return () => {
      window.clearInterval(scoreInterval);
      window.clearInterval(taskInterval);
      window.clearInterval(wearableInterval);
      window.clearInterval(suggestionInterval);
    };
  }, [fetchScore, fetchTasks, fetchWearable, fetchSuggestions, fetchIncidents]);

  return {
    currentScore,
    tasks,
    currentTask,
    tomorrowTasks,
    setTomorrowTasks,
    wearable,
    suggestions,
    incidentCounts,
    loading,
  };
};
