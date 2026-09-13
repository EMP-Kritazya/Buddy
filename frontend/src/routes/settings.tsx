import { createFileRoute } from "@tanstack/react-router";
import SettingsPage from "@/pages/SettingsPage";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: "Settings — Buddy" },
      { name: "description", content: "Tune Buddy: tracking, devices and preferences." },
      { property: "og:title", content: "Settings — Buddy" },
      {
        property: "og:description",
        content: "Tune Buddy: tracking, devices and preferences.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: SettingsPage,
});
