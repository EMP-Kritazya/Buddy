# Complete Buddy dashboard

## Build
- Extend the typed preview data with the current task, spoken tasks, suggestions, score series, wearable messages, incident state, and daily summary requested.
- Replace the dashboard placeholder with a full-height two-panel workspace: a fixed live-status rail and independently scrolling main content.
- Add interactive task status cycling, inline task creation, mark-done/skip behavior, a ticking clock, and the expandable day summary.
- Render the live and full-day charts with Recharts, including the incident markers, matching tooltips, responsive sizing, and the existing semantic color tokens.
- Add the compact tablet/mobile status bar while hiding the left rail, without changing other pages.

## Technical details
- Keep all dashboard data sourced from `previewData.ts`, with Phase 2 integration comments at the data and polling boundaries.
- Use the existing Button component for controls and existing font/color tokens only.
- Preserve the current `/dashboard` metadata and navigation to `/journal`.
- Add only dashboard-scoped animation styles needed for task transitions and summary expansion, with reduced-motion handling.

## Verification
- Check desktop, laptop, and mobile layouts; independent scrolling; chart rendering; clock updates; task controls; inline task entry; summary expansion; and Journal navigation.
- Confirm no overflow, runtime errors, or build errors.
