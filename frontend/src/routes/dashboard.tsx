import { createFileRoute } from "@tanstack/react-router";
import DashboardPage from "@/pages/DashboardPage";

export const Route = createFileRoute("/dashboard")({
  head: () => ({
    meta: [
      { title: "Today — Buddy" },
      { name: "description", content: "Your live focus score, tasks and distractions today." },
      { property: "og:title", content: "Today — Buddy" },
      {
        property: "og:description",
        content: "Your live focus score, tasks and distractions today.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: DashboardPage,
});
