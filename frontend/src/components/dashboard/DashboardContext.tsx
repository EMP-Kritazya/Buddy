import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { previewData } from "@/data/previewData";
import type { User } from "@/types";

type DashboardContextValue = {
  user: User;
  saveUser: (user: User) => void;
};

const DashboardContext = createContext<DashboardContextValue | null>(null);

export function DashboardProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState(previewData.user);

  useEffect(() => {
    const saved = window.localStorage.getItem("buddy_user");
    if (!saved) return;
    try {
      const parsed = JSON.parse(saved) as Partial<User>;
      setUser({ ...previewData.user, ...parsed });
    } catch {
      window.localStorage.removeItem("buddy_user");
    }
  }, []);

  const saveUser = (nextUser: User) => {
    setUser(nextUser);
    window.localStorage.setItem("buddy_user", JSON.stringify(nextUser));
    // Phase 2: PATCH /api/users/profile
  };

  return <DashboardContext.Provider value={{ user, saveUser }}>{children}</DashboardContext.Provider>;
}

const fallbackValue: DashboardContextValue = { user: previewData.user, saveUser: () => {} };

export function useDashboardUser() {
  // Falls back to preview data if rendered outside the provider (e.g. during hot reload).
  return useContext(DashboardContext) ?? fallbackValue;
}