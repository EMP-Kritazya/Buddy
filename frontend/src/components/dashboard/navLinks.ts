import { BookOpen, Compass, House, Radio } from "lucide-react";

export const dashboardNavLinks = [
  { to: "/dashboard", label: "Home", icon: House },
  { to: "/live", label: "Live", icon: Radio },
  { to: "/discover", label: "Discover", icon: Compass },
  { to: "/journal", label: "Journal", icon: BookOpen },
] as const;