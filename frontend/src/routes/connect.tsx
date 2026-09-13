import { createFileRoute } from "@tanstack/react-router";

import ConnectPage from "@/pages/ConnectPage";

export const Route = createFileRoute("/connect")({
  head: () => ({
    meta: [
      { title: "Connect Buddy Wearable" },
      { name: "description", content: "Connect your Buddy Wearable and finish setup." },
      { property: "og:title", content: "Connect Buddy Wearable" },
      { property: "og:description", content: "Connect your Buddy Wearable and finish setup." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: ConnectPage,
});
