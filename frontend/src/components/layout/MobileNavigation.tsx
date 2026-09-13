import { Link } from "@tanstack/react-router";

import { dashboardNavLinks } from "@/components/dashboard/navLinks";

export function MobileNavigation() {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-50 h-12 border-t border-border bg-canvas md:hidden" aria-label="Mobile navigation">
      <ul className="grid h-full grid-cols-4">
        {dashboardNavLinks.map((link) => {
          const Icon = link.icon;
          return (
            <li key={link.to}>
              <Link to={link.to} activeOptions={{ exact: true }} className="flex h-12 flex-col items-center justify-center gap-0.5 text-[10px] text-ink-3" activeProps={{ className: "text-accent" }}>
                <Icon className="size-[15px]" aria-hidden="true" />
                <span>{link.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}