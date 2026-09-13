import { createFileRoute } from "@tanstack/react-router";

import LivePage from "@/pages/LivePage";

export const Route = createFileRoute("/live")({
  head: () => ({ meta: [
    { title: "Live Focus — Buddy" },
    { name: "description", content: "Track your live focus score, session, and Buddy commentary." },
    { property: "og:title", content: "Live Focus — Buddy" },
    { property: "og:description", content: "Track your live focus score, session, and Buddy commentary." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary" },
  ] }),
  component: LivePage,
});