import { useEffect, useState } from "react";

import { onboardingService } from "@/services/onboardingService";

export type UserProfile = {
  name: string;
  email: string;
  university: string;
  major: string;
  peakTime: string;
  goal: string;
};

export const useUserProfile = () => {
  const [profile, setProfile] = useState<UserProfile>({
    name: "there",
    email: "",
    university: "",
    major: "",
    peakTime: "",
    goal: "",
  });

  useEffect(() => {
    const stored = JSON.parse(window.localStorage.getItem("buddy_user") || "{}");
    const onboarding = onboardingService.getStored();

    if (stored.name || onboarding?.name) {
      setProfile({
        name: stored.name || onboarding?.name || "there",
        email: stored.email || "",
        university: stored.university || onboarding?.university || "",
        major: stored.major || onboarding?.major || "",
        peakTime: stored.peakTime || onboarding?.peakTime || "",
        goal: stored.goal || onboarding?.goal || "",
      });
    }

    // Phase 2: apiClient.get("/api/users/profile").then((data) => data && setProfile(data))
  }, []);

  return { profile, setProfile };
};
