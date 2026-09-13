import { apiClient } from "@/lib/apiClient";
import { stamp } from "@/lib/previewAdapters";
import { previewData } from "@/data/previewData";
import type { ApiIncident } from "@/types/api";

export type { ApiIncident as Incident } from "@/types/api";

export const incidentService = {
  getToday: async (): Promise<ApiIncident[] | null> => {
    // Phase 2: GET /api/incidents/today
    const real = await apiClient.get<ApiIncident[]>("/api/incidents/today");
    if (real) return real;

    return previewData.incidents.map((incident) => ({
      id: incident.id,
      timestamp: stamp(incident.time),
      app_name: incident.app,
      duration_secs: incident.duration,
      score: incident.score / 100,
      trigger: incident.type === "hard" ? 2 : 1,
      intervened: incident.intervened,
      gemini_response: previewData.wearableMessages[0]?.message ?? "",
    }));
  },
};
