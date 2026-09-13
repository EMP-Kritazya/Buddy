import { createFileRoute } from "@tanstack/react-router";
import JournalPage from "@/pages/JournalPage";

export const Route = createFileRoute("/journal")({
  head: () => ({
    meta: [
      { title: "Journal — Buddy" },
      { name: "description", content: "The written record of your day, goals and drift." },
      { property: "og:title", content: "Journal — Buddy" },
      {
        property: "og:description",
        content: "The written record of your day, goals and drift.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: JournalPage,
});
