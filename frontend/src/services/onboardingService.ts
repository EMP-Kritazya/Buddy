export interface OnboardingData {
  name: string;
  email: string;
  university: string;
  major: string;
  level: string;
  studyHours: string;
  peakTime: string;
  distraction: string;
  needs: string[];
  goal: string;
}

export const onboardingService = {
  submit: async (data: OnboardingData) => {
    // Store in localStorage always so the dashboard can read name etc.
    window.localStorage.setItem("buddy_onboarding", JSON.stringify(data));

    const existing = JSON.parse(window.localStorage.getItem("buddy_user") || "{}");
    window.localStorage.setItem(
      "buddy_user",
      JSON.stringify({
        ...existing,
        name: data.name,
        email: data.email || existing.email || "",
        university: data.university,
        major: data.major,
        peakTime: data.peakTime,
        goal: data.goal,
        onboardingComplete: true,
      }),
    );

    // Phase 2: POST `${API_BASE}/api/users/onboarding` with the bearer token.
    // Gemini is seeded with this data by the backend automatically.
    return { success: true };
  },

  getStored: (): OnboardingData | null => {
    if (typeof window === "undefined") return null;
    const stored = window.localStorage.getItem("buddy_onboarding");
    return stored ? (JSON.parse(stored) as OnboardingData) : null;
  },
};
