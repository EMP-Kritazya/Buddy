export const authService = {
  signup: async (email: string, _password: string) => {
    // Phase 2: POST `${API_BASE}/api/auth/signup` with { email, password }
    // then localStorage.setItem("buddy_token", data.token)
    const existing = JSON.parse(window.localStorage.getItem("buddy_user") || "{}");
    window.localStorage.setItem("buddy_user", JSON.stringify({ ...existing, email }));
    return { success: true };
  },

  login: async (_email: string, _password: string) => {
    // Phase 2: POST `${API_BASE}/api/auth/login` with { email, password }
    // then localStorage.setItem("buddy_token", data.token)
    const stored = window.localStorage.getItem("buddy_user");
    return stored ? { success: true } : { success: false };
  },

  logout: () => {
    window.localStorage.removeItem("buddy_user");
    window.localStorage.removeItem("buddy_token");
    window.localStorage.removeItem("buddy_onboarding");
  },
};
