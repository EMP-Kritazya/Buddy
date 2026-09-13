import { apiClient } from "@/lib/apiClient";
import { previewData } from "@/data/previewData";
import type { CommentaryItem, GeminiSuggestion } from "@/types";

export const geminiService = {
  getLiveCommentary: async (): Promise<CommentaryItem[] | null> => {
    // Phase 2: GET /api/gemini/commentary (polled every 30s, new items prepended)
    const real = await apiClient.get<CommentaryItem[]>("/api/gemini/commentary");
    return real ?? previewData.liveCommentary;
  },

  getDayAnalysis: async (): Promise<CommentaryItem[] | null> => {
    // Phase 2: GET /api/gemini/day-analysis (refreshed every 5 min)
    const real = await apiClient.get<CommentaryItem[]>("/api/gemini/day-analysis");
    return real ?? previewData.dayCommentary;
  },

  getSuggestions: async (): Promise<GeminiSuggestion[] | null> => {
    // Phase 2: GET /api/gemini/suggestions (refreshed every 5 min)
    const real = await apiClient.get<GeminiSuggestion[]>("/api/gemini/suggestions");
    return real ?? previewData.geminiSuggestions;
  },

  getCurrentSuggestion: async (): Promise<GeminiSuggestion | null> => {
    // Phase 2: GET /api/gemini/suggestion/current
    const real = await apiClient.get<GeminiSuggestion>("/api/gemini/suggestion/current");
    return real ?? previewData.geminiSuggestions[0] ?? null;
  },
};
