# Buddy sign-up and sign-in pages

## Build
- Replace both placeholder pages with a shared responsive two-column account layout using the existing Buddy colors and typography.
- Add the distinct sign-up and sign-in copy, underline-only text fields, compact score preview, and mobile/tablet visibility rules.
- Add client-side validation with field-level coral messages and route valid submissions to onboarding or dashboard.

## Verify
- Check desktop, tablet, and mobile layouts for visibility, spacing, and overflow.
- Confirm validation states, home links, cross-links, and successful form navigation.
- Confirm the preview builds without errors.

## Technical details
- Use semantic HTML forms, React state, Zod schemas, and TanStack Router navigation.
- Keep presentation within the two page files and reuse a small shared auth component without adding dependencies.
