import { createFileRoute } from "@tanstack/react-router";
import OnboardingPage from "@/pages/OnboardingPage";

export const Route = createFileRoute("/onboarding")({
  head: () => ({
    meta: [
      { title: "Set up Buddy" },
      { name: "description", content: "Answer a few questions and connect your devices." },
      { property: "og:title", content: "Set up Buddy" },
      {
        property: "og:description",
        content: "Answer a few questions and connect your devices.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: OnboardingPage,
});
