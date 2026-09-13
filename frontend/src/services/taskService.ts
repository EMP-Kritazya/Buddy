import { apiClient } from "@/lib/apiClient";
import { previewData } from "@/data/previewData";
import type { SpokenTask, TomorrowTask } from "@/types";
import type { ApiCurrentTask } from "@/types/api";

export const taskService = {
  getToday: async (): Promise<SpokenTask[] | null> => {
    // Phase 2: GET /api/tasks/today (polled every 60s)
    const real = await apiClient.get<SpokenTask[]>("/api/tasks/today");
    return real ?? previewData.spokenTasks;
  },

  getCurrent: async (): Promise<ApiCurrentTask | null> => {
    // Phase 2: GET /api/tasks/current (polled every 60s)
    const real = await apiClient.get<ApiCurrentTask>("/api/tasks/current");
    if (real) return real;

    const task = previewData.currentTask;
    return {
      id: task.id,
      title: task.title,
      due: task.due,
      status: task.status,
      minutes_left: task.minutesLeft,
    };
  },

  getTomorrow: async (): Promise<TomorrowTask[] | null> => {
    // Phase 2: GET /api/tasks/tomorrow
    const real = await apiClient.get<TomorrowTask[]>("/api/tasks/tomorrow");
    return real ?? previewData.tomorrowTasks;
  },

  updateStatus: async (id: string, status: string) => {
    // Phase 2: PATCH /api/tasks/:id with { status }
    await apiClient.patch(`/api/tasks/${id}`, { status });
    return { success: true };
  },

  addTomorrow: async (title: string, priority: string) => {
    // Phase 2: POST /api/tasks/tomorrow with { title, priority }
    const real = await apiClient.post<{ id: string; title: string; priority: string }>("/api/tasks/tomorrow", {
      title,
      priority,
    });
    return real ?? { id: Date.now().toString(), title, priority };
  },
};
