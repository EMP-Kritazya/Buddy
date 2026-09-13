import { createFileRoute } from "@tanstack/react-router";

import DiscoverPage from "@/pages/DiscoverPage";

export const Route = createFileRoute("/discover")({
  head: () => ({ meta: [
    { title: "Discover Your Day — Buddy" },
    { name: "description", content: "Review your daily focus patterns, interruptions, and next steps." },
    { property: "og:title", content: "Discover Your Day — Buddy" },
    { property: "og:description", content: "Review your daily focus patterns, interruptions, and next steps." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary" },
  ] }),
  component: DiscoverPage,
});