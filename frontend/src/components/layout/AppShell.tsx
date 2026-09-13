import { useRouterState } from "@tanstack/react-router";
import type { ReactNode } from "react";

import { DashboardProvider } from "@/components/dashboard/DashboardContext";
import { MobileNavigation } from "./MobileNavigation";
import { TopNavigation } from "./TopNavigation";

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const dashboardRoutes = ["/dashboard", "/live", "/discover", "/journal"];
  const showNav = dashboardRoutes.includes(pathname);
  const isFullWidthPage = [
    "/",
    "/login",
    "/signup",
    "/onboarding",
    "/download",
    "/connect",
    "/dashboard", "/live", "/discover",
  ].includes(pathname);

  return (
    <DashboardProvider>
      <div className="relative min-h-screen bg-canvas">
        {showNav ? <TopNavigation /> : null}
        <main
          className={`relative mx-auto grid w-full grid-cols-1 ${
            isFullWidthPage ? "max-w-none gap-0 px-0" : "max-w-[1280px] gap-6 px-6 md:grid-cols-12"
          } ${showNav && !isFullWidthPage ? "py-10 pb-24 md:pb-10" : "py-0"}`}
        >
          <div className={isFullWidthPage ? "min-w-0" : "col-span-1 md:col-span-12"}>{children}</div>
        </main>
        {showNav ? <MobileNavigation /> : null}
      </div>
    </DashboardProvider>
  );
}
