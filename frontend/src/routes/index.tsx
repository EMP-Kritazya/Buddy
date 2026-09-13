import { createFileRoute } from "@tanstack/react-router";
import LandingPage from "@/pages/LandingPage";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Buddy — a calm companion for focused work" },
      {
        name: "description",
        content:
          "Buddy watches your focus, records distractions and writes you an honest daily journal.",
      },
      { property: "og:title", content: "Buddy — a calm companion for focused work" },
      {
        property: "og:description",
        content:
          "Buddy watches your focus, records distractions and writes you an honest daily journal.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: LandingPage,
});
