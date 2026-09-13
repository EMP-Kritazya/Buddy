import { createFileRoute } from "@tanstack/react-router";
import HistoryPage from "@/pages/HistoryPage";

export const Route = createFileRoute("/history")({
  head: () => ({
    meta: [
      { title: "History — Buddy" },
      { name: "description", content: "How your focus has moved across days and weeks." },
      { property: "og:title", content: "History — Buddy" },
      {
        property: "og:description",
        content: "How your focus has moved across days and weeks.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: HistoryPage,
});
