import { createFileRoute } from "@tanstack/react-router";

import DownloadPage from "@/pages/DownloadPage";

export const Route = createFileRoute("/download")({
  head: () => ({
    meta: [
      { title: "Download Buddy" },
      { name: "description", content: "Install Buddy and begin your personalized focus setup." },
      { property: "og:title", content: "Download Buddy" },
      {
        property: "og:description",
        content: "Install Buddy and begin your personalized focus setup.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: DownloadPage,
});