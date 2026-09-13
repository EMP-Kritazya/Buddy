export type TaskPriority = "high" | "medium" | "low";
export type TaskStatus = "not_started" | "in_progress" | "done";
export type SpokenTaskStatus = "missed" | "in_progress" | "todo" | "done";
export type IncidentType = "hard" | "soft";

export interface User {
  name: string;
  lastName: string;
  email: string;
  university: string;
  major: string;
  peakTime: string;
  goal: string;
  score: number;
  currentApp: string;
  currentWindow: string;
  sessionDuration: number;
  wearableConnected: boolean;
}

export interface TomorrowTask {
  id: string;
  title: string;
  priority: "high" | "medium";
}

export interface CommentaryItem {
  id: string;
  time: string | null;
  period?: string | null;
  text: string;
  type: "positive" | "warning" | "incident";
}

export interface ScorePoint {
  time: string;
  score: number;
}

export interface Task {
  id: string;
  title: string;
  due: string;
  priority: TaskPriority;
  status: TaskStatus;
}

export interface Incident {
  id: string;
  time: string;
  app: string;
  score: number;
  duration: number;
  type: IncidentType;
  intervened: boolean;
}

export interface CurrentTask {
  id: string;
  title: string;
  due: string;
  status: "in_progress" | "todo" | "done";
  minutesLeft: number;
}

export interface SpokenTask {
  id: string;
  title: string;
  due: string;
  status: SpokenTaskStatus;
}

export interface GeminiSuggestion {
  id: string;
  text: string;
  updatedMinsAgo: number;
}

export interface WearableMessage {
  time: string;
  message: string;
  type: IncidentType;
}

export interface DailySummary {
  focusTime: string;
  avgScore: number;
  incidents: number;
  tasksCompleted: number;
  tasksTotal: number;
  strongestPeriod: string;
  geminiReflection: string;
  tomorrowSuggestion: string;
}

export interface JournalEntry {
  date: string;
  goals: string[];
  incidents: string[];
  suggestion: string;
  markdown: string;
}

export interface PreviewData {
  user: User;
  currentTask: CurrentTask;
  spokenTasks: SpokenTask[];
  geminiSuggestions: GeminiSuggestion[];
  liveScores: ScorePoint[];
  todayScores: ScorePoint[];
  wearableMessages: WearableMessage[];
  liveScoreHistory: ScorePoint[];
  dayScoreHistory: ScorePoint[];
  tasks: Task[];
  incidents: Incident[];
  journal: JournalEntry;
  suggestion: string;
  strongestPeriod: string;
  summary: DailySummary;
  tomorrowTasks: TomorrowTask[];
  liveCommentary: CommentaryItem[];
  dayCommentary: CommentaryItem[];
}

export type ScoreBand = "productive" | "drifting" | "incident";
