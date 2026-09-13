# Restructure Buddy dashboard into Home, Live, Discover, and Journal

## Build
- Extend the existing typed preview data without removing current fields: add the expanded profile, tomorrow tasks, live commentary, and day commentary, plus the requested Phase 2 API notes.
- Add shared client-side profile state initialized safely after hydration from `buddy_user`, falling back to `previewData.user`; profile edits save back to local storage.
- Replace the dashboard-only shell with a shared sticky Buddy navigation for `/dashboard`, `/live`, `/discover`, and `/journal`, including active links, profile dropdown, edit-profile modal, settings navigation, and sign-out behavior.
- Add the tablet hamburger menu and the 48px mobile bottom tab bar while preserving access to the profile controls.
- Rebuild `/dashboard` as Home with the greeting, current-task/productivity/connection panel, priority and wearable-suggestion panel, interactive tomorrow-task list, Live CTA, and Discover CTA.
- Create `/live` with three live stats, the 30-minute Recharts line chart, wearable messages, sticky commentary, and the rotating 45-second simulated commentary feed.
- Create `/discover` with four summary stats, the full-day Recharts area chart, incidents, tomorrow suggestion, export controls, and sticky day analysis.
- Keep the existing `/journal` page content unchanged while placing it within the new shared navigation.

## Technical details
- Add `/live` and `/discover` route files with unique title, description, Open Graph, and Twitter metadata; keep the generated route tree untouched.
- Consolidate the four dashboard navigation destinations into one shared definition so desktop, tablet, and mobile navigation stay synchronized.
- Reuse the existing semantic color and typography tokens, Recharts dependency, and shared Button control; add no packages, shadows, or new visual palette.
- Split the restructure into focused shared components for profile/navigation, charts/commentary, and each page rather than keeping one oversized dashboard file.
- Use client-safe initialization for time and local storage to avoid server-rendering mismatches.
- Preserve the requested Phase 2 comments at profile, tomorrow-task, live-commentary, day-analysis, and export boundaries without adding backend calls.

## Verification
- Check all four navigation links, active states, desktop dropdown, tablet menu, mobile bottom tabs, profile edit/save/cancel, settings link, and sign-out redirect.
- Check Home greeting, score states, both panels, task completion, inline tomorrow-task creation with Enter/Escape, and both page CTAs.
- Check Live stats, chart, wearable rows, sticky commentary, and simulated item insertion/fade behavior.
- Check Discover stats, chart, incident details, day commentary, tomorrow suggestion, and Journal navigation.
- Verify desktop, laptop, tablet, and 390px mobile layouts for overflow and overlap, then confirm clean type checks, runtime console, and build diagnostics.
