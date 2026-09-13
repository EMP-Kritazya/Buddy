import { apiClient } from "@/lib/apiClient";
import { previewData } from "@/data/previewData";
import type { WearableMessage } from "@/types";
import type { WearableStatus } from "@/types/api";

export const wearableService = {
  getStatus: async (): Promise<WearableStatus | null> => {
    // Phase 2: GET /api/wearable/status (polled every 10s)
    const real = await apiClient.get<WearableStatus>("/api/wearable/status");
    if (real) return real;

    const latest = previewData.wearableMessages[0];
    return {
      connected: previewData.user.wearableConnected,
      last_trigger_time: latest?.time ?? "",
      last_trigger_message: latest?.message ?? "",
    };
  },

  getMessages: async (): Promise<WearableMessage[] | null> => {
    // Phase 2: GET /api/wearable/messages
    const real = await apiClient.get<WearableMessage[]>("/api/wearable/messages");
    return real ?? previewData.wearableMessages;
  },
};
