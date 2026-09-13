import type { PreviewData } from "@/types";

export const previewData: PreviewData = {
  user: {
    name: "Sandesh",
    lastName: "Dhakal",
    email: "sandesh@uta.edu",
    university: "University of Texas at Arlington",
    major: "Computer Science",
    peakTime: "Afternoon",
    goal: "Finish senior design and maintain 3.9 GPA",
    score: 84,
    currentApp: "Visual Studio Code",
    currentWindow: "Senior Design Dashboard",
    sessionDuration: 42,
    wearableConnected: true,
  },
  currentTask: {
    id: "2",
    title: "Senior design until 10 PM",
    due: "22:00",
    status: "in_progress",
    minutesLeft: 28,
  },
  spokenTasks: [
    { id: "1", title: "Email professor", due: "18:00", status: "missed" },
    { id: "2", title: "Senior design until 10 PM", due: "22:00", status: "in_progress" },
    { id: "3", title: "Review slides", due: "21:00", status: "todo" },
  ],
  geminiSuggestions: [
    { id: "1", text: "Break your senior design into three parts before 10 PM.", updatedMinsAgo: 4 },
    { id: "2", text: "Start with the hardest part first.", updatedMinsAgo: 18 },
    { id: "3", text: "Close YouTube before 9 PM.", updatedMinsAgo: 35 },
  ],
  liveScores: [
    { time: "21:05", score: 76 },
    { time: "21:10", score: 80 },
    { time: "21:12", score: 83 },
    { time: "21:14", score: 12 },
    { time: "21:18", score: 45 },
    { time: "21:22", score: 67 },
    { time: "21:28", score: 79 },
    { time: "21:32", score: 84 },
    { time: "21:35", score: 84 },
  ],
  todayScores: [
    { time: "08:00", score: 62 },
    { time: "10:00", score: 81 },
    { time: "12:00", score: 70 },
    { time: "14:00", score: 86 },
    { time: "16:00", score: 78 },
    { time: "18:00", score: 83 },
    { time: "21:14", score: 12 },
    { time: "21:30", score: 76 },
    { time: "21:35", score: 84 },
  ],
  wearableMessages: [
    { time: "21:14", message: "You've been on League for 4 minutes. Want to come back?", type: "hard" },
    { time: "19:30", message: "You've been focused for 2 hours. Take a short break.", type: "soft" },
    { time: "17:15", message: "Senior design deadline is in 3 hours. On track?", type: "soft" },
  ],
  liveScoreHistory: [
    { time: "21:00", score: 76 },
    { time: "21:05", score: 80 },
    { time: "21:10", score: 83 },
    { time: "21:14", score: 12 },
    { time: "21:20", score: 45 },
    { time: "21:25", score: 67 },
    { time: "21:30", score: 76 },
    { time: "21:35", score: 84 },
  ],
  dayScoreHistory: [
    { time: "08:00", score: 62 },
    { time: "10:00", score: 81 },
    { time: "12:00", score: 70 },
    { time: "14:00", score: 86 },
    { time: "16:00", score: 78 },
    { time: "18:00", score: 83 },
    { time: "21:14", score: 12 },
    { time: "21:30", score: 76 },
    { time: "21:35", score: 84 },
  ],
  tasks: [
    {
      id: "1",
      title: "Email professor",
      due: "Today at 6:00 PM",
      priority: "high",
      status: "not_started",
    },
    {
      id: "2",
      title: "Senior design until 10 PM",
      due: "Today at 10:00 PM",
      priority: "high",
      status: "in_progress",
    },
  ],
  incidents: [
    {
      id: "1",
      time: "21:14",
      app: "League of Legends",
      score: 12,
      duration: 54,
      type: "hard",
      intervened: true,
    },
  ],
  journal: {
    date: "12 Sep 2026",
    goals: ["Email professor", "Senior design until 10 PM"],
    incidents: ["21:14 — League of Legends (score 12, 54s)"],
    suggestion: "Email your professor before opening anything else tomorrow.",
    markdown: `# Buddy Journal — 12 Sep 2026\n\n## Goals\n- Email professor\n- Senior design until 10 PM\n\n## Incidents\n- 21:14 — League of Legends during senior-design block (score 12, 54s).\n\n## Suggestion\nEmail first tomorrow before opening anything else.`,
  },
  suggestion: "Email your professor before opening anything else tomorrow.",
  strongestPeriod: "2:00 PM – 6:00 PM",
  summary: {
    focusTime: "4h 22m",
    avgScore: 84,
    incidents: 1,
    tasksCompleted: 1,
    tasksTotal: 3,
    strongestPeriod: "2:00 PM – 6:00 PM",
    geminiReflection: "Your strongest work was between 2PM and 6PM. One interruption at 9:14 pulled your score down, but you recovered in under 2 minutes.",
    tomorrowSuggestion: "Email your professor before opening anything else tomorrow.",
  },
  tomorrowTasks: [
    { id: "t1", title: "Email professor first thing", priority: "high" },
    { id: "t2", title: "Start thesis outline", priority: "medium" },
  ],
  liveCommentary: [
    { id: "c1", time: "21:35", text: "You've been focused for 42 minutes. Strong work.", type: "positive" },
    { id: "c2", time: "21:30", text: "VS Code open. You're on task.", type: "positive" },
    { id: "c3", time: "21:14", text: "League detected. Score hit 12. You recovered fast — good.", type: "incident" },
    { id: "c4", time: "21:05", text: "Focus building steadily after a slow start.", type: "positive" },
    { id: "c5", time: "20:45", text: "Score dipping. YouTube in background?", type: "warning" },
    { id: "c6", time: "20:30", text: "Good momentum. Keep the current app open.", type: "positive" },
  ],
  dayCommentary: [
    { id: "d1", time: "21:14", period: null, text: "League of Legends for 54 seconds. Score hit 12. Buddy intervened.", type: "incident" },
    { id: "d2", time: null, period: "18:00 – 21:00", text: "Strongest 3-hour block. Avg score 86. VS Code the entire time.", type: "positive" },
    { id: "d3", time: null, period: "14:00 – 16:00", text: "Deep focus period. Productivity peaked at 91.", type: "positive" },
    { id: "d4", time: "12:00", period: null, text: "Short dip after lunch. Recovered within 20 minutes.", type: "warning" },
    { id: "d5", time: null, period: "08:00 – 10:00", text: "Slow morning start. Score averaged 62.", type: "warning" },
  ],
};

// Phase 2: replace previewData with real API calls
// scoreService.ts     → GET /api/scores/live (30s poll)
// taskService.ts      → GET /api/tasks/today (60s poll)
// wearableService.ts  → GET /api/wearable/status (10s poll)
// summaryService.ts   → GET /api/summary/today (on demand)
// GET /api/users/profile → user object
// GET /api/tasks/tomorrow → tomorrowTasks
// GET /api/gemini/commentary → liveCommentary (30s poll)
// GET /api/gemini/day-analysis → dayCommentary
