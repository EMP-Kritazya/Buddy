import { createFileRoute } from "@tanstack/react-router";
import SignupPage from "@/pages/SignupPage";

export const Route = createFileRoute("/signup")({
  head: () => ({
    meta: [
      { title: "Create your Buddy account" },
      { name: "description", content: "Start tracking your focus with Buddy." },
      { property: "og:title", content: "Create your Buddy account" },
      { property: "og:description", content: "Start tracking your focus with Buddy." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: SignupPage,
});
