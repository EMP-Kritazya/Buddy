import type { TriggerLevel } from "@/lib/format";

/** Normalised shapes returned by the backend (scores are 0–1, snake_case fields). */

export interface ScoreSample {
  timestamp: string;
  score: number;
  trigger: TriggerLevel;
}

export interface CurrentScore {
  score: number;
  app_name: string;
  window_title: string;
  session_duration: number;
  trigger: TriggerLevel;
}

export interface ApiCurrentTask {
  id: string;
  title: string;
  due: string;
  status: string;
  minutes_left: number;
}

export interface WearableStatus {
  connected: boolean;
  last_trigger_time: string;
  last_trigger_message: string;
}

export interface ApiDailySummary {
  focus_time_mins: number;
  avg_score: number;
  incidents: number;
  tasks_completed: number;
  tasks_total: number;
  strongest_period: string;
  gemini_reflection: string;
  tomorrow_suggestion: string;
}

export interface ApiIncident {
  id: string;
  timestamp: string;
  app_name: string;
  duration_secs: number;
  score: number;
  trigger: 1 | 2;
  intervened: boolean;
  gemini_response: string;
}
