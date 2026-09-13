import { createFileRoute } from "@tanstack/react-router";
import LoginPage from "@/pages/LoginPage";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign in — Buddy" },
      { name: "description", content: "Sign in to your Buddy account." },
      { property: "og:title", content: "Sign in — Buddy" },
      { property: "og:description", content: "Sign in to your Buddy account." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: LoginPage,
});
