import { useCallback, useEffect, useState } from "react";

import { geminiService } from "@/services/geminiService";
import { scoreService } from "@/services/scoreService";
import { wearableService } from "@/services/wearableService";
import type { CommentaryItem, WearableMessage } from "@/types";
import type { CurrentScore, ScoreSample } from "@/types/api";

/** Live page data — everything refreshes together every 30 seconds. */
export const useLiveData = () => {
  const [liveScores, setLiveScores] = useState<ScoreSample[] | null>(null);
  const [wearableMessages, setWearableMessages] = useState<WearableMessage[] | null>(null);
  const [commentary, setCommentary] = useState<CommentaryItem[] | null>(null);
  const [currentScore, setCurrentScore] = useState<CurrentScore | null>(null);
  const [loading, setLoading] = useState({ scores: true, commentary: true });

  const fetchLive = useCallback(async () => {
    // Phase 2: these hit /api/scores/live, /api/scores/current, /api/wearable/messages, /api/gemini/commentary
    const [scores, current, messages, comments] = await Promise.all([
      scoreService.getLive(),
      scoreService.getCurrent(),
      wearableService.getMessages(),
      geminiService.getLiveCommentary(),
    ]);

    setLiveScores(scores);
    setCurrentScore(current);
    setWearableMessages(messages);

    if (comments) {
      setCommentary((previous) => {
        if (!previous) return comments;
        const seen = new Set(previous.map((item) => item.id));
        const fresh = comments.filter((item) => !seen.has(item.id));
        return fresh.length > 0 ? [...fresh, ...previous] : previous;
      });
    }

    setLoading({ scores: false, commentary: false });
  }, []);

  useEffect(() => {
    void fetchLive();
    const interval = window.setInterval(() => void fetchLive(), 30000);
    return () => window.clearInterval(interval);
  }, [fetchLive]);

  return { liveScores, currentScore, wearableMessages, commentary, loading };
};
